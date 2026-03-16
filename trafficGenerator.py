from config import Config
from dperfSetup import dperf
from system_monitor import SystemMonitor
from threading import Thread
import csv
import os
import time


class TrafficGenerator:
    """Traffic Generator Management Class

    Encapsulates multiple dperf pairs and a shared SystemMonitor,
    providing a unified interface for traffic testing management.
    """

    def __init__(self, config: Config, log_path: str = "./logs", output_path: str = "./results",
                 redis_host: str = "localhost", redis_port: int = 6379, redis_db: int = 0,
                 enable_redis: bool = True):
        """Initialize traffic generator

        Args:
            config: Configuration object
            log_path: Log output path
            output_path: Results output path
            redis_host: Redis host address
            redis_port: Redis port
            redis_db: Redis database index
            enable_redis: Whether to enable Redis storage
        """
        self.config = config
        self.log_path = log_path
        self.output_path = output_path
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.enable_redis = enable_redis

        # Get pair count
        self.pair_count = len(config.test.traffic_generator.pairs)
        print(f"[TrafficGenerator] Detected {self.pair_count} pair(s)")

        # Establish shared SystemMonitor (only one needed for the entire machine)
        self.monitor = SystemMonitor(
            config=config,
            output_path=output_path,
            log_path=log_path,
            redis_host=redis_host,
            redis_port=redis_port,
            redis_db=redis_db,
            enable_redis=enable_redis,
        )

        # Establish multiple dperf pairs
        self.pairs = []
        for i in range(self.pair_count):
            pair = dperf(
                config=config,
                pair_index=i,
                log_path=log_path,
                output_path=f"{output_path}/dperf_pair{i}_results.csv",
                redis_host=redis_host,
                redis_port=redis_port,
                redis_db=redis_db,
                enable_redis=enable_redis
            )
            self.pairs.append(pair)
            print(f"[TrafficGenerator] Pair {i} established")

    def connect(self):
        """Connect to remote host (includes monitor and all pairs)"""
        print("[TrafficGenerator] Starting connection...")

        # Connect monitor
        self.monitor.connect()
        print("[TrafficGenerator] Monitor connected")

        # Connect all pairs
        for i, pair in enumerate(self.pairs):
            pair.connect()
            print(f"[TrafficGenerator] Pair {i} connected")

        print("[TrafficGenerator] All connections established")

    def disconnect(self):
        """Disconnect all connections"""
        print("[TrafficGenerator] Starting disconnection...")

        # Disconnect all pairs
        for i, pair in enumerate(self.pairs):
            pair.disconnect()
            print(f"[TrafficGenerator] Pair {i} disconnected")

        # Disconnect monitor
        self.monitor.disconnect()
        print("[TrafficGenerator] Monitor disconnected")

        print("[TrafficGenerator] All connections disconnected")

    def setup_env(self, pair_indices: list|None = None, dry_run: bool = False):
        """Setup test environment

        Args:
            pair_indices: List of pair indices to setup, setup all if None
            dry_run: If True, show configuration without executing
        """
        if pair_indices is None:
            pair_indices = list(range(self.pair_count))

        print(f"[TrafficGenerator] Starting environment setup (Pairs: {pair_indices})...")

        for i in pair_indices:
            if i < len(self.pairs):
                print(f"[TrafficGenerator] Setting up Pair {i} environment...")
                self.pairs[i].setupEnv(dry_run=dry_run)
                print(f"[TrafficGenerator] Pair {i} environment setup completed")
            else:
                print(f"[TrafficGenerator] Warning: Pair {i} does not exist")

        print("[TrafficGenerator] Environment setup completed")

    def clearEnv(self, pair_indices: list|None = None, dry_run: bool = False):
        """Clear environment

        Args:
            pair_indices: List of pair indices to clear, clear all if None
            dry_run: If True, show what would be cleared without executing
        """
        if pair_indices is None:
            pair_indices = list(range(self.pair_count))

        print(f"[TrafficGenerator] Starting environment clearance (Pairs: {pair_indices})...")

        for i in pair_indices:
            if i < len(self.pairs):
                print(f"[TrafficGenerator] Clearing Pair {i} environment...")
                self.pairs[i].clearEnv(dry_run=dry_run)
                print(f"[TrafficGenerator] Pair {i} environment cleared")
            else:
                print(f"[TrafficGenerator] Warning: Pair {i} does not exist")

        print("[TrafficGenerator] Environment clearance completed")

    def run_test(self, pair_indices: list|None = None, enable_monitor: bool = True,
                 parallel: bool = False, dry_run: bool = False):
        """Execute test

        Args:
            pair_indices: List of pair indices to test, test all if None
            enable_monitor: Whether to enable monitoring
            parallel: Whether to execute multiple pair tests in parallel
            dry_run: If True, skip actual dperf traffic generation

        Returns:
            dict: Test results, containing server/client output and monitoring data for each pair
        """
        if pair_indices is None:
            pair_indices = list(range(self.pair_count))

        print(f"[TrafficGenerator] Starting test (Pairs: {pair_indices}, Parallel: {parallel}, Monitor: {enable_monitor}, DryRun: {dry_run})...")

        results = {}

        # Start monitoring (skip in dry run mode)
        if enable_monitor and not dry_run:
            self.monitor.start()
            time.sleep(2)  # Ensure monitoring is started

        try:
            if parallel:
                # Execute all pair tests in parallel
                results = self._run_parallel(pair_indices, dry_run=dry_run)
            else:
                # Execute each pair test sequentially
                results = self._run_sequential(pair_indices, dry_run=dry_run)
        finally:
            # Stop monitoring
            if enable_monitor and not dry_run:
                self.monitor.stop()

        # Add monitoring data to results
        results['monitor_data'] = self.monitor.get_data() if not dry_run else []

        # 產生跨 pair 彙總報告
        if not dry_run:
            self.outputSummaryReport(self.output_path)

        print("[TrafficGenerator] Test completed")
        return results

    def _run_sequential(self, pair_indices: list, dry_run: bool = False):
        """Execute tests sequentially

        Args:
            pair_indices: List of pair indices to test
            dry_run: If True, skip actual dperf traffic generation

        Returns:
            dict: Test results
        """
        results = {}
        for i in pair_indices:
            if i < len(self.pairs):
                print(f"[TrafficGenerator] Executing Pair {i} test...")
                result = self.pairs[i].runPairTest(dry_run=dry_run)
                results[f'pair_{i}'] = result
            else:
                print(f"[TrafficGenerator] Warning: Pair {i} does not exist")
        return results

    def _run_parallel(self, pair_indices: list, dry_run: bool = False):
        """Execute tests in parallel

        Args:
            pair_indices: List of pair indices to test
            dry_run: If True, skip actual dperf traffic generation

        Returns:
            dict: Test results
        """
        results = {}
        threads = []

        def run_pair(pair_index):
            if pair_index < len(self.pairs):
                result = self.pairs[pair_index].runPairTest(dry_run=dry_run)
                results[f'pair_{pair_index}'] = result

        # Establish and start all test threads
        for i in pair_indices:
            t = Thread(target=run_pair, args=(i,), name=f"PairTest-{i}")
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        return results

    @staticmethod
    def _parse_cc(cc_str: str) -> int:
        """將 '2k'、'1m'、'500' 等 cc 字串轉換為整數"""
        s = str(cc_str).strip().lower()
        if s.endswith('k'):
            return int(float(s[:-1]) * 1_000)
        elif s.endswith('m'):
            return int(float(s[:-1]) * 1_000_000)
        try:
            return int(s)
        except ValueError:
            return 0

    def outputSummaryReport(self, output_path: str):
        """產生跨所有 pair 的彙總 CSV（dperf_summary.csv）。

        欄位格式：Metric | pair0_server | pair0_client | ... | total_server | total_client | Unit
        """
        os.makedirs(output_path, exist_ok=True)
        out_file = os.path.join(output_path, 'dperf_summary.csv')
        n = len(self.pairs)
        tg = self.config.test.traffic_generator

        # 建立 header
        header = ['Metric']
        for i in range(n):
            header += [f'pair{i}_server', f'pair{i}_client']
        header += ['total_server', 'total_client', 'Unit']

        def make_row(metric, sv_list, cv_list, total_s, total_c, unit=''):
            row = [metric]
            for s, c in zip(sv_list, cv_list):
                row += [s, c]
            row += [total_s, total_c, unit]
            return row

        def safe_sum(vals):
            nums = [v for v in vals if isinstance(v, (int, float))]
            return sum(nums) if nums else 'N/A'

        def safe_sum_round(vals, ndigits=6):
            nums = [v for v in vals if isinstance(v, (int, float))]
            return round(sum(nums), ndigits) if nums else 'N/A'

        rows = []

        # ── 元數據 ──────────────────────────────────────────────
        rows.append(make_row(
            'protocol',
            [p.pair.protocol for p in self.pairs],
            [p.pair.protocol for p in self.pairs],
            '-', '-',
        ))
        rows.append(make_row(
            'pci_address',
            [p.pair.server.server_nic_pci for p in self.pairs],
            [p.pair.client.client_nic_pci for p in self.pairs],
            '-', '-',
        ))
        rows.append(make_row(
            'apv_port',
            [p.pair.apv_server_port for p in self.pairs],
            [p.pair.apv_client_port for p in self.pairs],
            '-', '-',
        ))
        rows.append(make_row(
            'duration',
            [tg.duration] * n,
            [tg.duration] * n,
            tg.duration, tg.duration, 's',
        ))
        cc_vals = [p.pair.client.cc for p in self.pairs]
        total_cc = sum(self._parse_cc(cc) for cc in cc_vals)
        rows.append(make_row('session', cc_vals, cc_vals, total_cc, total_cc, 'count'))

        # ── 原始指標 ─────────────────────────────────────────────
        METRIC_UNITS = {
            'ackDup': 'count', 'ackRt': 'count',
            'arpRx': 'packet', 'arpTx': 'packet',
            'badRx': 'packet', 'dropTx': 'packet',
            'ierrors': 'count', 'imissed': 'packet', 'oerrors': 'count',
            'bitsRx': 'bits', 'bitsTx': 'bits',
            'finRt': 'count', 'finRx': 'packet', 'finTx': 'packet',
            'http2XX': 'count', 'httpErr': 'count',
            'httpGet': 'count', 'httpPost': 'count',
            'icmpRx': 'packet', 'icmpTx': 'packet',
            'otherRx': 'packet',
            'pktRx': 'packet', 'pktTx': 'packet',
            'pushRt': 'count',
            'rstRx': 'packet', 'rstTx': 'packet',
            'skClose': 'count', 'skCon': 'count',
            'skErr': 'count', 'skOpen': 'count',
            'synRt': 'count', 'synRx': 'packet', 'synTx': 'packet',
            'tcpDrop': 'packet', 'tcpRx': 'packet', 'tcpTx': 'packet',
            'tosRx': 'packet',
            'udpDrop': 'packet', 'udpRx': 'packet', 'udpTx': 'packet',
        }

        all_keys = set()
        for p in self.pairs:
            if p.serverOutput:
                all_keys.update(p.serverOutput.keys())
            if p.clientOutput:
                all_keys.update(p.clientOutput.keys())

        for key in sorted(all_keys):
            sv = [p.serverOutput.get(key, 'N/A') if p.serverOutput else 'N/A' for p in self.pairs]
            cv = [p.clientOutput.get(key, 'N/A') if p.clientOutput else 'N/A' for p in self.pairs]
            rows.append(make_row(key, sv, cv, safe_sum(sv), safe_sum(cv), METRIC_UNITS.get(key, '')))

        # ── 衍生指標 ─────────────────────────────────────────────
        DERIVED_UNITS = {
            'avg_throughput_gbps': 'Gbps',
            'max_throughput_gbps': 'Gbps',
            'avg_throughput_pps':  'pps',
            'max_throughput_pps':  'pps',
            'avg_cps':             'cps',
            'max_cps':             'cps',
            'max_cc':              'count',
        }
        for metric, unit in DERIVED_UNITS.items():
            sv = [p.serverDerived.get(metric, 'N/A') for p in self.pairs]
            cv = [p.clientDerived.get(metric, 'N/A') for p in self.pairs]
            rows.append(make_row(metric, sv, cv,
                                 safe_sum_round(sv), safe_sum_round(cv), unit))

        with open(out_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows)

        print(f"[TrafficGenerator] 彙總報告已輸出至 {out_file}")

    def get_pair(self, pair_index: int):
        """Retrieve specified pair instance

        Args:
            pair_index: pair index

        Returns:
            dperf: pair instance, returns None if index is invalid
        """
        if 0 <= pair_index < len(self.pairs):
            return self.pairs[pair_index]
        return None

    def get_monitor(self):
        """Retrieve monitor instance

        Returns:
            SystemMonitor: monitor instance
        """
        return self.monitor

    def get_pair_count(self):
        """Retrieve pair count

        Returns:
            int: pair count
        """
        return self.pair_count
