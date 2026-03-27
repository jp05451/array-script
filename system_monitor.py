from ssh_executor import SSHExecutor
from output_handler import OutputHandler
from RedisDB import RedisHandler
from config import Config
import csv
import os
import re
import time
from datetime import datetime
from threading import Thread, Lock


class SystemMonitor:
    """Monitor CPU and memory usage of the Traffic Generator host and APV device.

    Takes a Config object and output_path at construction time; extracts all
    connection parameters from the config so callers do not need to pass them
    individually.  Manages its own CSV output in real-time during monitoring.

    Redis support is reserved for future expansion and can be enabled via the
    enable_redis flag.

    Typical usage::

        monitor = SystemMonitor(config=cfg, output_path="./results")
        monitor.connect()
        monitor.start()
        # ... run tests ...
        monitor.stop()
        monitor.disconnect()
        data = monitor.get_data()
    """

    def __init__(
        self,
        config: Config,
        output_path: str = "./results",
        log_path: str = "./logs",
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        enable_redis: bool = False,
    ):
        """Initialize SystemMonitor.

        Args:
            config: Test configuration object.  Connection details for both the
                Traffic Generator and APV are extracted from this object.
            output_path: Directory where system_monitor.csv will be written.
            log_path: Directory where SSH session log files are stored.
            redis_host: Redis server hostname (used only when enable_redis=True).
            redis_port: Redis server port.
            redis_db: Redis database index.
            enable_redis: Set True to persist monitoring data to Redis.
        """
        self._config = config
        self.monitoring = False
        self.monitor_data = []
        self._monitor_thread = None

        # Ensure output and log directories exist
        self._output_path = output_path or "./results"
        self._log_path = log_path or "./logs"
        os.makedirs(self._output_path, exist_ok=True)
        os.makedirs(self._log_path, exist_ok=True)

        # Traffic Generator SSH executor
        tg = config.test.traffic_generator
        self._tg_executor = SSHExecutor(
            tg.management_ip,
            tg.management_port,
            tg.username,
            tg.password,
            log_path=os.path.join(self._log_path, "system_monitor_tg.log"),
        )

        # APV SSH executor (optional — enabled only when all APV fields are set)
        self._apv_latest_cpu: float | None = None  # latest reading shared with main loop
        self._apv_latest_cpu_lock: Lock = Lock()   # protects _apv_latest_cpu across threads
        self._apv_data: list[dict] = []            # full history of APV readings (own array)
        self._apv_thread: Thread | None = None
        self._apv_executor: SSHExecutor | None = None
        self._apv_enable_password: str | None = config.test.apv_enable_password or None

        # enable_password is optional — APV just needs host/user/pass to connect
        self.apv_enabled: bool = all([
            config.test.apv_management_ip,
            config.test.apv_username,
            config.test.apv_password,
        ])
        if self.apv_enabled:
            self._apv_executor = SSHExecutor(
                config.test.apv_management_ip,
                config.test.apv_management_port or 22,
                config.test.apv_username,
                config.test.apv_password,
                log_path=os.path.join(self._log_path, "system_monitor_apv.log"),
            )

        # SLB stats executor — dedicated third SSH connection for SLB stats collection
        self._slb_executor: SSHExecutor | None = None
        self._slb_enable_password: str | None = config.test.apv_enable_password or None
        self._slb_stats_thread: Thread | None = None
        self._slb_stats_raw: list[dict] = []   # [{timestamp, raw_output, parsed}, ...]
        self._per_pair_slb: dict = {}           # {pair_index: {'vs': ..., 'rs': ...}}
        if self.apv_enabled:
            self._slb_executor = SSHExecutor(
                config.test.apv_management_ip,
                config.test.apv_management_port or 22,
                config.test.apv_username,
                config.test.apv_password,
                log_path=os.path.join(self._log_path, "system_monitor_slb.log"),
            )

        # Redis (reserved for future expansion)
        self._enable_redis = enable_redis
        self._redis_handler: RedisHandler | None = None
        if self._enable_redis:
            self._init_redis(redis_host, redis_port, redis_db)

    # -------------------------------------------------------------------------
    # Connection Management
    # -------------------------------------------------------------------------

    def connect(self):
        """Connect SSH sessions to all monitored hosts."""
        self._tg_executor.connect(persistent_session=True)
        if self.apv_enabled and self._apv_executor:
            self._apv_executor.connect(persistent_session=True)
            self._enter_apv_enable_mode()
        if self.apv_enabled and self._slb_executor:
            self._slb_executor.connect(persistent_session=True, keepalive_interval=30)
            self._enter_slb_enable_mode()


    def disconnect(self):
        """Disconnect all SSH sessions and close Redis connection."""
        self._tg_executor.close()
        if self.apv_enabled and self._apv_executor:
            self._apv_executor.close()
        if self.apv_enabled and self._slb_executor:
            self._slb_executor.close()
        self._close_redis()

    # -------------------------------------------------------------------------
    # Monitoring Lifecycle
    # -------------------------------------------------------------------------

    def start(self):
        """Start monitoring in background threads.

        The main monitoring loop polls Traffic Generator CPU and memory every
        second.  When APV monitoring is enabled, a separate daemon thread polls
        the APV every second and shares the latest value with the main loop.
        A third daemon thread sleeps until 10 s before expected test end,
        then executes ``show statistics slb all`` once and exits.

        Monitoring data is collected in-memory; call outputMonitorResult() after
        stop() to write all CSV files.
        """
        if self.monitoring:
            print("[SystemMonitor] Monitoring is already in progress")
            return

        self.monitoring = True

        self._monitor_thread = Thread(
            target=self._monitor_loop,
            name="SystemMonitor",
        )
        self._monitor_thread.start()

        if self.apv_enabled:
            self._apv_thread = Thread(
                target=self._apv_monitor_loop,
                name="APVMonitor",
                daemon=True,
            )
            self._apv_thread.start()

        if self.apv_enabled and self._slb_executor:
            self._slb_stats_thread = Thread(
                target=self._slb_stats_monitor_loop,
                name="SLBStatsMonitor",
                daemon=True,
            )
            self._slb_stats_thread.start()

    def stop(self):
        """Stop all monitoring threads and wait for them to finish."""
        self.monitoring = False
        print("[SystemMonitor] Stopping monitoring...")

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
            if self._monitor_thread.is_alive():
                print("[SystemMonitor] Warning: Monitoring thread failed to exit properly")

        if self._apv_thread and self._apv_thread.is_alive():
            # APV thread is daemon=True and checks self.monitoring — wait up to
            # one full APV poll cycle (30 s command timeout + 3 s sleep)
            self._apv_thread.join(timeout=35)

        if self._slb_stats_thread and self._slb_stats_thread.is_alive():
            self._slb_stats_thread.join(timeout=5)
            if self._slb_stats_thread.is_alive():
                print("[SystemMonitor] Warning: SLB stats thread failed to exit properly")

    def is_monitoring(self) -> bool:
        """Return True if monitoring is currently active."""
        return self.monitoring

    def get_data(self) -> list:
        """Return the merged TG+APV monitoring data (one entry per second).

        Each data point is a dict with keys:
            timestamp, tg_cpu_usage, tg_ram_used, tg_ram_total, tg_ram_usage,
            and optionally apv_cpu_usage (when APV monitoring is enabled).
        """
        return self.monitor_data

    def get_apv_data(self) -> list:
        """Return the raw APV polling history (one entry per successful poll, ~every 3 s).

        Each entry is a dict with keys: timestamp, apv_cpu_usage.
        Returns an empty list when APV monitoring is disabled.
        """
        return self._apv_data

    def get_slb_stats_raw(self) -> list[dict]:
        """Return all periodic SLB stats samples collected during the test.

        Each entry is a dict with keys:
            timestamp (str): Collection time as 'YYYY-MM-DD HH:MM:SS'.
            raw_output (str): Raw output of ``show statistics slb all``.

        Pass raw_output to ``APVSetup.parseSLBStats()`` to parse into VS/RS dicts.
        Returns an empty list when APV monitoring is disabled or no samples were collected.
        """
        return self._slb_stats_raw

    def get_per_pair_slb(self) -> dict:
        """Return per-pair SLB statistics matched by _do_slb_collection.

        Returns an empty dict when APV monitoring is disabled or no samples were collected.
        """
        return self._per_pair_slb

    def outputMonitorResult(self) -> None:
        """Write system_monitor.csv and apv_slb_stats.csv from collected data.

        Must be called after stop() to ensure all data has been collected.
        system_monitor.csv is always written (empty if no data).
        apv_slb_stats.csv is skipped when no SLB data was collected.
        """
        # Write system_monitor.csv from in-memory data
        csv_path = os.path.join(self._output_path, "system_monitor.csv")
        self._write_csv_header(csv_path)
        for data_point in self.monitor_data:
            self._append_csv_row(csv_path, data_point)
        print(f"[SystemMonitor] Monitoring data saved to {csv_path}")

        # Write apv_slb_stats.csv if we have per-pair SLB data
        if not self._per_pair_slb:
            return
        parsed = self._slb_stats_raw[0].get('parsed') if self._slb_stats_raw else None
        if parsed is None:
            return
        from APVSetup import APVSetup as _APV
        os.makedirs(self._output_path, exist_ok=True)
        csv_path = os.path.join(self._output_path, 'apv_slb_stats.csv')

        # 建立 identifier → pair_label 反向查找表
        id_to_pair: dict[str, str] = {}
        for pair_idx, slb in self._per_pair_slb.items():
            for kind in ('vs', 'rs'):
                entry = slb.get(kind)
                if entry:
                    idf = f"{entry['name']} ({entry['ip']}:{entry['port']}) [{entry['status']}]"
                    id_to_pair[idf] = f'pair_{pair_idx}'

        rows = []
        for vs in parsed.get('vs', []):
            identifier = f"{vs['name']} ({vs['ip']}:{vs['port']}) [{vs['status']}]"
            pair_label = id_to_pair.get(identifier, '-')
            for metric, value in vs['metrics'].items():
                unit = _APV._SLB_METRIC_UNITS.get(metric, '')
                rows.append(['VS', pair_label, metric, value, unit])
        for rs in parsed.get('rs', []):
            identifier = f"{rs['name']} ({rs['ip']}:{rs['port']}) [{rs['status']}]"
            pair_label = id_to_pair.get(identifier, '-')
            for metric, value in rs['metrics'].items():
                unit = _APV._SLB_METRIC_UNITS.get(metric, '')
                rows.append(['RS', pair_label, metric, value, unit])

        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Type', 'Pair', 'Metric', 'Value', 'Unit'])
            writer.writerows(rows)

        print(f"[SystemMonitor] SLB 統計資料已輸出至 {csv_path}")

    # -------------------------------------------------------------------------
    # Traffic Generator Metrics Collection
    # -------------------------------------------------------------------------

    def _collect_tg_cpu(self) -> float:
        """Collect Traffic Generator CPU usage percentage via SSH.

        Uses ``top -bn1`` to get a single snapshot; extracts the idle percentage
        and returns 100 - idle.

        Returns:
            CPU usage as a float in the range 0–100, or 0.0 on failure.
        """
        try:
            cpu_cmd = "top -bn1 | grep 'Cpu(s)' | awk '{print $8}'"
            result = self._tg_executor.execute_command(cpu_cmd)
            output = OutputHandler.clean_ansi(result[0]) if result else ""
            lines = [line.strip() for line in output.split('\n') if line.strip()]
            for line in reversed(lines):
                try:
                    if line and not line.startswith('[') and '#' not in line:
                        return 100.0 - float(line)
                except ValueError:
                    continue
        except Exception as e:
            print(f"[SystemMonitor] Error collecting TG CPU: {e}")
        return 0.0

    def _collect_tg_memory(self) -> tuple:
        """Collect Traffic Generator memory usage via SSH.

        Uses ``free -m`` to retrieve used/total memory in megabytes.

        Returns:
            Tuple of (ram_used_mb: int, ram_total_mb: int, ram_usage_percent: float).
            Returns (0, 0, 0.0) on failure.
        """
        try:
            ram_cmd = "free -m | grep Mem | awk '{print $3, $2}'"
            result = self._tg_executor.execute_command(ram_cmd)
            output = OutputHandler.clean_ansi(result[0]) if result else ""
            lines = [line.strip() for line in output.split('\n') if line.strip()]
            for line in reversed(lines):
                try:
                    if line and not line.startswith('[') and '#' not in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            ram_used = int(parts[0])
                            ram_total = int(parts[1])
                            ram_usage = round((ram_used / ram_total * 100), 2) if ram_total > 0 else 0.0
                            return ram_used, ram_total, ram_usage
                except (ValueError, IndexError):
                    continue
        except Exception as e:
            print(f"[SystemMonitor] Error collecting TG memory: {e}")
        return 0, 0, 0.0

    # -------------------------------------------------------------------------
    # APV Metrics Collection
    # -------------------------------------------------------------------------

    def _enter_apv_enable_mode(self):
        """Enter APV privileged (enable) mode at connection time.

        APV CLI flow:
          > enable          — APV responds with 'Password:'
          Password: <pass>  — APV enters enable prompt (#)

        Note: 'Password:' does not match prompt detectors ($/#/>), so
        execute_in_session times out then returns; we send the password next.
        """
        assert self._apv_executor is not None
        shell = self._apv_executor
        assert shell is not None, "APV SSH session not established; call connect() first"
        print("[APVMonitor] Entering enable mode...")
        shell.execute_command('enable')
        shell.execute_command(self._apv_enable_password or '')
        print("[APVMonitor] Enable mode entered")

    def _enter_slb_enable_mode(self):
        """Enter APV privileged (enable) mode for the dedicated SLB stats session.

        Identical flow to _enter_apv_enable_mode but uses _slb_executor.
        Enable mode is entered once at connect() time and held for the duration
        of the test so each _do_slb_collection() call does not need to re-authenticate.
        """
        shell = self._slb_executor
        assert shell is not None, "SLB SSH session not established; call connect() first"
        print("[SLBStatsMonitor] Entering enable mode...")
        
        shell.execute_command('enable')
        shell.execute_command(self._slb_enable_password or '')
        shell.execute_command('no pager')
        print("[SLBStatsMonitor] Enable mode entered")

    def _parse_apv_cpu(self, output: str) -> float | None:
        """Parse CPU usage from APV 'show statistics cpu' output.

        Expected format in output::

            CPU Utilization 7 %

        Args:
            output: Raw string returned by the APV SSH session.

        Returns:
            CPU usage as a float, or None if the pattern is not found.
        """
        cleaned = OutputHandler.clean_ansi(output)
        match = re.search(r'CPU\s+Utilization\s+(\d+(?:\.\d+)?)\s*%', cleaned, re.IGNORECASE)
        return float(match.group(1)) if match else None

    def _do_slb_collection(self) -> None:
        """Execute ``show statistics slb all`` once; parse, match, and store results.

        The SLB session must already be connected and in enable mode.
        Pagination is suppressed by ``no pager`` issued in _enter_slb_enable_mode.
        Stores parsed stats in _slb_stats_raw and matched per-pair result in
        _per_pair_slb.  Does NOT write any CSV — call outputMonitorResult() instead.
        """
        assert self._slb_executor is not None
        shell = self._slb_executor
        try:
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"[SLBStatsMonitor] Collecting SLB stats at {ts}...")
            result = shell.execute_command('show statistics slb all')
            full_output = result[0] if result else ''
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Parse raw output (APVSetup.parseSLBStats is a pure static method)
            from APVSetup import APVSetup as _APV
            parsed = _APV.parseSLBStats(full_output)

            # Match VS/RS to pairs inline (naming convention: {protocol}_vs_{idx})
            pairs = self._config.test.traffic_generator.pairs
            per_pair_slb = {i: {'vs': None, 'rs': None} for i in range(len(pairs))}
            for vs in parsed.get('vs', []):
                m = re.search(r'_vs_(\d+)$', vs['name'])
                if m:
                    idx = int(m.group(1))
                    if idx in per_pair_slb:
                        per_pair_slb[idx]['vs'] = vs
            for rs in parsed.get('rs', []):
                m = re.search(r'_rs_(\d+)$', rs['name'])
                if m:
                    idx = int(m.group(1))
                    if idx in per_pair_slb:
                        per_pair_slb[idx]['rs'] = rs

            self._slb_stats_raw.append({'timestamp': ts, 'raw_output': full_output, 'parsed': parsed})
            self._per_pair_slb = per_pair_slb
        except Exception as e:
            print(f"[SLBStatsMonitor] Error collecting SLB stats: {e}")

    def _slb_stats_monitor_loop(self) -> None:
        """Background daemon: waits until 10 s before test end, then samples once.

        The SLB SSH session is already connected and in enable mode (established
        in connect()).  This thread calculates the expected test duration from
        config, sleeps until 10 s before expected end, then calls
        _do_slb_collection() if monitoring is still active.
        """
        from dperfSetup import dperf as _dperf
        tg = self._config.test.traffic_generator
        total_seconds = (
            _dperf._parse_time_to_seconds(tg.duration) +
            _dperf._parse_time_to_seconds(tg.server_buffer_time) +
            _dperf._parse_time_to_seconds(tg.client_buffer_time)
        )
        wait_seconds = max(total_seconds - 10, 0)
        print(f"[SLBStatsMonitor] 總時長 {total_seconds:.0f}s，將在 {wait_seconds:.0f}s 後採樣")
        time.sleep(wait_seconds)
        if not self.monitoring:
            print("[SLBStatsMonitor] 監控已停止，跳過採樣")
            return
        if self._slb_executor is not None:
            try:
                self._slb_executor.execute_command('')
            except Exception: 
                self._slb_executor.connect()
                self._enter_slb_enable_mode()
            self._enter_slb_enable_mode()
        self._do_slb_collection()
        print("[SLBStatsMonitor] 採樣完成，執行緒結束")

    def _apv_monitor_loop(self):
        """APV CPU polling loop running in a dedicated daemon thread.

        Polls 'show statistics cpu' every 3 seconds (APV CLI is slow) and
        stores the latest parsed value in self._apv_latest_cpu for the main
        monitor loop to read.
        """
        assert self._apv_executor is not None
        shell = self._apv_executor
        assert shell is not None, "APV SSH session not established; call connect() first"
        print("[APVMonitor] Starting APV CPU monitoring...")
        while self.monitoring:
            try:
                output = shell.execute_command(
                    'show statistics cpu'
                )
                cpu = self._parse_apv_cpu(output[0] if output else '')
                if cpu is not None:
                    # Update shared latest value (lock protects concurrent read in main loop)
                    with self._apv_latest_cpu_lock:
                        self._apv_latest_cpu = cpu
                    # Append to own history array — one entry per successful poll (~3 s)
                    self._apv_data.append({
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'apv_cpu_usage': round(cpu, 2),
                    })
                else:
                    print("[APVMonitor] Warning: Could not parse CPU from output")
            except Exception as e:
                print(f"[APVMonitor] Error reading CPU: {e}")
            time.sleep(1)
        print("[APVMonitor] APV CPU monitoring stopped")

    # -------------------------------------------------------------------------
    # CSV Output
    # -------------------------------------------------------------------------

    def _build_csv_headers(self) -> list:
        """Build the CSV header row based on which monitors are enabled.

        Returns:
            List of column name strings.
        """
        headers = [
            'Timestamp',
            'TG_CPU_Usage_Percent',
            'TG_RAM_Used_MB',
            'TG_RAM_Total_MB',
            'TG_RAM_Usage_Percent',
        ]
        if self.apv_enabled:
            headers.append('APV_CPU_Usage_Percent')
        return headers

    def _write_csv_header(self, csv_path: str):
        """Create (or overwrite) the CSV file and write the header row.

        Args:
            csv_path: Absolute path to the output CSV file.
        """
        with open(csv_path, 'w', newline='') as f:
            csv.writer(f).writerow(self._build_csv_headers())

    def _append_csv_row(self, csv_path: str, data_point: dict):
        """Append a single monitoring data point as a CSV row.

        Args:
            csv_path: Absolute path to the output CSV file.
            data_point: Dict produced by the monitor loop.
        """
        row = [
            data_point['timestamp'],
            data_point['tg_cpu_usage'],
            data_point['tg_ram_used'],
            data_point['tg_ram_total'],
            data_point['tg_ram_usage'],
        ]
        if self.apv_enabled:
            apv_val = data_point.get('apv_cpu_usage')
            row.append('' if apv_val is None else apv_val)
        with open(csv_path, 'a', newline='') as f:
            csv.writer(f).writerow(row)

    # -------------------------------------------------------------------------
    # Redis (reserved for future expansion)
    # -------------------------------------------------------------------------

    def _init_redis(self, host: str, port: int, db: int):
        """Initialize the Redis connection.

        Called at construction time when enable_redis=True.  Stores the handler
        in self._redis_handler; sets it to None if connection fails so that all
        _save_to_redis calls become no-ops.

        Args:
            host: Redis hostname.
            port: Redis port.
            db: Redis database index.
        """
        try:
            self._redis_handler = RedisHandler(host=host, port=port, db=db)
            if self._redis_handler.is_connected():
                print("[SystemMonitor] Redis connected successfully")
            else:
                print("[SystemMonitor] Redis connection failed, using local storage only")
                self._redis_handler = None
        except Exception as e:
            print(f"[SystemMonitor] Redis init failed: {e}, using local storage only")
            self._redis_handler = None

    def _close_redis(self):
        """Close the Redis connection if it is open."""
        if self._redis_handler:
            self._redis_handler.close()
            self._redis_handler = None

    def _save_to_redis(self, data_point: dict):
        """Persist a monitoring data point to Redis.

        This method is a no-op when Redis is disabled or unavailable, making it
        safe to call unconditionally from the monitor loop.  Extend this method
        when adding richer Redis storage (e.g. APV metrics, per-field keys).

        Args:
            data_point: Monitoring data point dict from the monitor loop.
        """
        if not (self._enable_redis and self._redis_handler and self._redis_handler.is_connected()):
            return
        try:
            self._redis_handler.save_monitor_data(
                pair_index=0,
                timestamp=data_point['timestamp'],
                cpu_usage=data_point['tg_cpu_usage'],
                ram_used=data_point['tg_ram_used'],
                ram_total=data_point['tg_ram_total'],
                ram_usage=data_point['tg_ram_usage'],
            )
        except Exception as e:
            print(f"[SystemMonitor] Redis write failed: {e}")

    def get_redis_monitor_data(self, start_time=None, end_time=None) -> list:
        """Retrieve monitoring data from Redis.

        Args:
            start_time: Optional start time filter.
            end_time: Optional end time filter.

        Returns:
            List of monitoring data records, or empty list if Redis is
            unavailable.
        """
        if self._redis_handler and self._redis_handler.is_connected():
            return self._redis_handler.get_monitor_data(0, start_time, end_time)
        return []

    # -------------------------------------------------------------------------
    # Main Monitor Loop
    # -------------------------------------------------------------------------

    def _monitor_loop(self):
        """Main monitoring loop — polls TG and APV metrics every second.

        Collects data points into self.monitor_data for later output.
        Call outputMonitorResult() after stop() to write the CSV.
        """
        self.monitor_data = []
        print("[SystemMonitor] Starting monitoring...")

        while self.monitoring:
            try:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                tg_cpu = round(self._collect_tg_cpu(), 2)
                tg_ram_used, tg_ram_total, tg_ram_usage = self._collect_tg_memory()

                data_point = {
                    'timestamp': timestamp,
                    'tg_cpu_usage': tg_cpu,
                    'tg_ram_used': tg_ram_used,
                    'tg_ram_total': tg_ram_total,
                    'tg_ram_usage': tg_ram_usage,
                }

                if self.apv_enabled:
                    with self._apv_latest_cpu_lock:
                        apv_raw = self._apv_latest_cpu
                    data_point['apv_cpu_usage'] = round(apv_raw, 2) if apv_raw is not None else None

                self.monitor_data.append(data_point)
                self._save_to_redis(data_point)

                time.sleep(1)

            except Exception as e:
                print(f"[SystemMonitor] Monitoring error: {e}")
                time.sleep(1)

        print("[SystemMonitor] Monitoring stopped")
