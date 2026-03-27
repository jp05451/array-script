from config import Config
from dperfSetup import dperf
from system_monitor import SystemMonitor
from APVSetup import APVSetup
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

        # APVSetup instance (managed internally)
        self.apv = APVSetup(config, log_path=log_path)

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
        """Connect to remote host (includes APV, monitor and all pairs)"""
        print("[TrafficGenerator] Starting connection...")

        # Connect APV
        self.apv.connect()
        print("[TrafficGenerator] APV connected")

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

        # Disconnect APV
        self.apv.disconnect()
        print("[TrafficGenerator] APV disconnected")

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

        # APV setup: clear existing config, configure LB, resolve port names
        if not dry_run:
            self.apv.clearEnv()
            self.apv.setupEnv(dry_run=dry_run)
            self.apv.resolvePortNames()

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
        try:
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

            # APV teardown
            if not dry_run:
                try: 
                    self.apv.clearEnv()
                except Exception as e:
                    print(f"[TrafficGenerator] Error occurred while clearing APV environment: {e}")
                    self.apv.connect()  # Attempt to reconnect APV and clear again
                    self.apv.clearEnv()

            print("[TrafficGenerator] Environment clearance completed")
        except Exception as e:
            print(f"[TrafficGenerator] Error during environment clearance: {e}")

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
            if enable_monitor and not dry_run:
                self.monitor.stop()
                self.monitor.outputMonitorResult()

        # Add monitoring data to results
        results['monitor_data'] = self.monitor.get_data() if not dry_run else []
        results['slb_stats_raw'] = self.monitor.get_slb_stats_raw() if not dry_run else []

        # Generate cross-pair summary report
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
        print("[TrafficGenerator] Executing tests in parallel for pairs: {pair_indices}...")
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
        
        print("[TrafficGenerator] =============== All parallel tests completed=============")

        return results

    @staticmethod
    def _parse_cc(cc_str: str) -> int:
        """Convert cc strings like '2k', '1m', '500' to integers"""
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
        """Generate cross-pair summary CSV (dperf_summary.csv).

        Field format: Metric | pair0_server | pair0_client | ... | total_server | total_client | Unit
        """
        os.makedirs(output_path, exist_ok=True)
        out_file = os.path.join(output_path, 'dperf_summary.csv')
        n = len(self.pairs)
        tg = self.config.test.traffic_generator

        # Build header
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

        # ── Metadata ──────────────────────────────────────────────
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

        # ── Raw Metrics ─────────────────────────────────────────────
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

        # ── Derived Metrics ─────────────────────────────────────────────
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

        print(f"[TrafficGenerator] Summary is output to {out_file}")

    def processSLBStats(self):
        """Append SLB statistics collected by monitor to per-pair CSV and summary CSV.

        Read data from monitor.get_per_pair_slb(), no need to pass apv object.
        Return silently if data not yet collected.
        """
        per_pair = self.monitor.get_per_pair_slb()
        if not per_pair:
            return
        try:
            self.appendSLBStats(per_pair)
        except Exception as e:
            print(f"[TrafficGenerator] fail to append SLB stats: {e}")

    def appendSLBStats(self, per_pair_slb: dict):
        """Append SLB statistics to per-pair CSV and summary CSV.

        Args:
            per_pair_slb: dict returned by matchSLBStatsToPairs()
                          {pair_index: {'vs': entry_or_None, 'rs': entry_or_None}}
        """
        # ── Append to per-pair CSV ─────────────────────────────────────────────
        for i, pair_obj in enumerate(self.pairs):
            slb = per_pair_slb.get(i, {'vs': None, 'rs': None})
            vs_entry = slb.get('vs')
            rs_entry = slb.get('rs')

            pair_csv = os.path.join(self.output_path, f'dperf_pair{i}_results.csv')
            if not os.path.exists(pair_csv):
                continue

            with open(pair_csv, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([])
                writer.writerow(['# SLB Statistics', '', '', ''])
                if vs_entry:
                    writer.writerow([f'slb_vs_name', vs_entry['name'], '', ''])
                    writer.writerow([f'slb_vs_status', vs_entry['status'], '', ''])
                    for metric, value in vs_entry['metrics'].items():
                        unit = APVSetup._SLB_METRIC_UNITS.get(metric, '')
                        writer.writerow([f'slb_vs_{metric}', value, '', unit])
                if rs_entry:
                    writer.writerow([f'slb_rs_name', rs_entry['name'], '', ''])
                    writer.writerow([f'slb_rs_status', rs_entry['status'], '', ''])
                    for metric, value in rs_entry['metrics'].items():
                        unit = APVSetup._SLB_METRIC_UNITS.get(metric, '')
                        writer.writerow([f'slb_rs_{metric}', value, '', unit])

        # ── Append to summary CSV ──────────────────────────────────────────────
        summary_csv = os.path.join(self.output_path, 'dperf_summary.csv')
        if not os.path.exists(summary_csv):
            return

        n = len(self.pairs)
        header = ['Metric']
        for i in range(n):
            header += [f'pair{i}_server', f'pair{i}_client']
        header += ['total_server', 'total_client', 'Unit']

        def safe_sum(vals):
            nums = [v for v in vals if isinstance(v, (int, float))]
            return sum(nums) if nums else 'N/A'

        def make_row(metric, sv_list, cv_list, total_s, total_c, unit=''):
            row = [metric]
            for s, c in zip(sv_list, cv_list):
                row += [s, c]
            row += [total_s, total_c, unit]
            return row

        # Collect all VS/RS metric keys (preserve order)
        vs_keys: list[str] = []
        rs_keys: list[str] = []
        seen_vs: set[str] = set()
        seen_rs: set[str] = set()
        for i in range(n):
            slb = per_pair_slb.get(i, {})
            vs_entry = slb.get('vs')
            rs_entry = slb.get('rs')
            if vs_entry:
                for k in vs_entry['metrics']:
                    if k not in seen_vs:
                        vs_keys.append(k)
                        seen_vs.add(k)
            if rs_entry:
                for k in rs_entry['metrics']:
                    if k not in seen_rs:
                        rs_keys.append(k)
                        seen_rs.add(k)

        slb_rows = []
        for key in vs_keys:
            sv = [per_pair_slb.get(i, {}).get('vs', {}) or {} for i in range(n)]
            vals = [e.get('metrics', {}).get(key, 'N/A') if e else 'N/A' for e in sv]
            slb_rows.append(make_row(
                f'slb_vs_{key}', vals, [''] * n,
                safe_sum(vals), '', APVSetup._SLB_METRIC_UNITS.get(key, '')
            ))
        for key in rs_keys:
            rv = [per_pair_slb.get(i, {}).get('rs', {}) or {} for i in range(n)]
            vals = [e.get('metrics', {}).get(key, 'N/A') if e else 'N/A' for e in rv]
            slb_rows.append(make_row(
                f'slb_rs_{key}', [''] * n, vals,
                '', safe_sum(vals), APVSetup._SLB_METRIC_UNITS.get(key, '')
            ))

        with open(summary_csv, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([])
            writer.writerow(['# SLB Statistics'] + [''] * (len(header) - 1))
            # writer.writerow(header)
            writer.writerows(slb_rows)

        print(f"[TrafficGenerator] SLB statistics appended to per-pair CSV and {summary_csv}")

    def printFormattedSummary(self):
        """Output test summary to console in vendor spec format.

        SLB statistics read from monitor.get_per_pair_slb(), no parameters need to be passed.
        """
        per_pair_slb = self.monitor.get_per_pair_slb()
        tg = self.config.test.traffic_generator

        def safe_sum(vals):
            nums = [v for v in vals if isinstance(v, (int, float))]
            return round(sum(nums), 6) if nums else 'N/A'

        # ── Global Summary ──────────────────────────────────────────
        total_cc = sum(self._parse_cc(p.pair.client.cc) for p in self.pairs)
        single_cc = self.pairs[0].pair.client.cc if self.pairs else 'N/A'

        print(f"\nTest duration: {tg.duration}")
        print(f"Session number: {single_cc} (single pair), {total_cc} (Total)")
        print(f"Max throughput: {safe_sum([p.clientDerived.get('max_throughput_gbps', 'N/A') for p in self.pairs])} (Gbps), "
              f"{safe_sum([p.clientDerived.get('max_throughput_pps', 'N/A') for p in self.pairs])} (pps)")
        print(f"Average Throughput: {safe_sum([p.clientDerived.get('avg_throughput_gbps', 'N/A') for p in self.pairs])} (Gbps), "
              f"{safe_sum([p.clientDerived.get('avg_throughput_pps', 'N/A') for p in self.pairs])} (pps)")
        print(f"Max concurrent Connection: {safe_sum([p.clientDerived.get('max_cc', 'N/A') for p in self.pairs])}")
        print(f"Max Connection Per Second: {safe_sum([p.clientDerived.get('max_cps', 'N/A') for p in self.pairs])} (cps)")
        print(f"Average Connection Per Second: {safe_sum([p.clientDerived.get('avg_cps', 'N/A') for p in self.pairs])} (cps)")

        # ── Per Pair ─────────────────────────────────────────────
        print("\nPairs:")
        for i, pair_obj in enumerate(self.pairs):
            pair = pair_obj.pair
            cd = pair_obj.clientDerived
            slb = per_pair_slb.get(i, {'vs': None, 'rs': None})
            vs_entry = slb.get('vs')
            rs_entry = slb.get('rs')

            print(f"- Traffic generator PCI: {pair.client.client_nic_pci}")
            print(f"  APV port number: {pair.apv_client_port}")
            print(f"  Session number: {pair.client.cc}")
            print(f"  Pair Max Throughput: {cd.get('max_throughput_gbps', 'N/A')} (Gbps), {cd.get('max_throughput_pps', 'N/A')} (pps)")
            print(f"  Pair Average Throughput: {cd.get('avg_throughput_gbps', 'N/A')} (Gbps), {cd.get('avg_throughput_pps', 'N/A')} (pps)")
            print(f"  Pair Max Connection: {cd.get('max_cc', 'N/A')}")
            print(f"  Pair Max Connection Per Second: {cd.get('max_cps', 'N/A')} (cps)")
            print(f"  Pair Average Connection Per Second: {cd.get('avg_cps', 'N/A')} (cps)")
            print("  SLB Statistics Data:")
            if vs_entry:
                print(f"  VS: {vs_entry['ip']}")
                for metric, value in vs_entry['metrics'].items():
                    print(f"    {metric}: {value}")
            if rs_entry:
                print(f"  RS: {rs_entry['ip']}")
                for metric, value in rs_entry['metrics'].items():
                    print(f"    {metric}: {value}")

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
