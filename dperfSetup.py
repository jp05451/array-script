from ssh_executor import SSHExecutor
from config import Config
from threading import Thread
from RedisDB import RedisHandler
import re
import os
import csv
from datetime import datetime
from typing import Optional


class dperf:
    def __init__(self, config: Config, pair_index: int = 0, log_path: Optional[str] = None, output_path: Optional[str] = None,
                 redis_host: str = "localhost", redis_port: int = 6379, redis_db: int = 0,
                 enable_redis: bool = True):
        self.config = config
        self.pair_index = pair_index
        self.pair = config.test.traffic_generator.pairs[pair_index]
        if log_path is None or log_path == "":
            log_path = "./logs"
        if not os.path.exists(log_path):
            os.makedirs(log_path, exist_ok=True)
        self.outputPath=output_path
        self.logPath=log_path
        self.executor = SSHExecutor(
            config.test.traffic_generator.management_ip,
            config.test.traffic_generator.management_port,
            config.test.traffic_generator.username,
            config.test.traffic_generator.password,
            log_path=f"{log_path}/dperf_pair{pair_index}.log",
        )
        # Create independent executors for server and client
        self.server_executor = SSHExecutor(
            config.test.traffic_generator.management_ip,
            config.test.traffic_generator.management_port,
            config.test.traffic_generator.username,
            config.test.traffic_generator.password,
            log_path=f"{log_path}/dperf_pair{pair_index}_server.log",
        )
        self.client_executor = SSHExecutor(
            config.test.traffic_generator.management_ip,
            config.test.traffic_generator.management_port,
            config.test.traffic_generator.username,
            config.test.traffic_generator.password,
            log_path=f"{log_path}/dperf_pair{pair_index}_client.log",
        )
        self.serverOutput = None
        self.clientOutput = None
        self.serverPerSecond = []
        self.clientPerSecond = []

        # Initialize Redis Handler
        self.enable_redis = enable_redis
        self.redis_handler = None
        if self.enable_redis:
            try:
                self.redis_handler = RedisHandler(host=redis_host, port=redis_port, db=redis_db)
                if self.redis_handler.is_connected():
                    print(f"[Pair {self.pair_index}] Redis enabled and connected successfully")
                else:
                    print(f"[Pair {self.pair_index}] Redis connection failed, will use local storage only")
                    self.redis_handler = None
            except Exception as e:
                print(f"[Pair {self.pair_index}] Redis initialization failed: {e}, will use local storage only")
                self.redis_handler = None
    def __del__(self):
        """Destructor to automatically disconnect from the server"""
        try:
            self.disconnect()
        except Exception:
            pass

    def connect(self):
        """Connect to remote host"""
        self.executor.connect(persistent_session=True)
        self.server_executor.connect(persistent_session=True)
        self.client_executor.connect(persistent_session=True)
        
    def disconnect(self):
        """Disconnect from remote host"""
        self.executor.close()
        self.server_executor.close()
        self.client_executor.close()

        # Close Redis connection
        if self.redis_handler:
            self.redis_handler.close()
    
    @staticmethod
    def _parse_time_to_seconds(s):
        """Parse a time string like '40s', '1m', '2h' into seconds (float)"""
        if s is None:
            return 0
        s = str(s).strip()
        if s.endswith('ms'):
            return float(s[:-2]) / 1000
        elif s.endswith('us'):
            return float(s[:-2]) / 1_000_000
        elif s.endswith('s'):
            return float(s[:-1])
        elif s.endswith('m'):
            return float(s[:-1]) * 60
        elif s.endswith('h'):
            return float(s[:-1]) * 3600
        else:
            try:
                return float(s)
            except Exception:
                return 0

    def _calc_duration(self, base_duration, buffer_time):
        # base_duration, buffer_time: strings like '40s', '1m', '2h'
        # Always converted to seconds for calculation, returns unit in 1s
        base_seconds = self._parse_time_to_seconds(base_duration)
        buffer_seconds = self._parse_time_to_seconds(buffer_time)
        result_seconds = max(base_seconds + buffer_seconds, 1)
        return f"{int(result_seconds)}s"

    def generateServerConfig(self):
        """Generate dperf server configuration file"""
        server_cfg = self.pair.server
        tg = self.config.test.traffic_generator
        # Calculate server duration (add client buffer time)
        duration = self._calc_duration(tg.duration, tg.client_buffer_time)

        config_lines = [
            "mode            server",
            f"tx_burst        {server_cfg.tx_burst}",
            f"cpu             {server_cfg.server_cpu_core}",
        ]

        if server_cfg.rss:
            config_lines.append("rss")

        config_lines.extend(
            [
                f"socket_mem      {server_cfg.socket_mem}",
                f"protocol        {self.pair.protocol}",
                f"duration        {duration}",
                f"payload_size    {self.pair.payload_size}",
                f"keepalive       {server_cfg.keepalive}",
                "",
                "# port           pci        addr        gateway        [mac]",
                f"port            {server_cfg.server_nic_pci}        {server_cfg.server_ip}        {server_cfg.server_gw}",
                "",
                "# addr_start      num",
                f"client          {self.pair.client.client_ip}    {self.pair.client.source_ip_nums}",
                "",
                "# addr_start      num",
                f"server          {server_cfg.server_ip}    1",
                "",
                "# port_start      num",
                f"listen          {server_cfg.listen_port}    {server_cfg.listen_port_nums}",
                "",
            ]
        )

        return "\n".join(config_lines)

    def generateClientConfig(self):
        """Generate dperf client configuration file"""
        client_cfg = self.pair.client
        tg = self.config.test.traffic_generator
        # Calculate client duration (add server buffer time)
        duration = self._calc_duration(tg.duration, tg.server_buffer_time)

        config_lines = [
            "mode            client",
            f"tx_burst        {client_cfg.tx_burst}",
            f"launch_num      {client_cfg.launch_num}",
            f"cpu             {client_cfg.client_cpu_core}",
        ]

        if client_cfg.rss:
            config_lines.append("rss")

        config_lines.extend(
            [
                f"socket_mem      {client_cfg.socket_mem}",
                f"protocol        {self.pair.protocol}",
                f"payload_size    {self.pair.payload_size}",
                f"duration        {duration}",
                "",
                f"cc              {client_cfg.cc}",
                f"keepalive       {client_cfg.keepalive}",
                "",
                "# port           pci             addr         gateway       [mac]",
                f"port            {client_cfg.client_nic_pci}    {client_cfg.client_ip}    {client_cfg.client_gw}",
                "",
                "# addr_start      num",
                f"client          {client_cfg.client_ip}    {client_cfg.source_ip_nums}",
                "",
                "# addr_start      num",
                f"server          {client_cfg.virtual_server_ip}    1",
                "",
                "# port_start      num",
                f"listen          {client_cfg.virtual_server_port}    {client_cfg.virtual_server_port_nums}",
                "",
            ]
        )

        return "\n".join(config_lines)

    def runPairTest(self, dry_run=False):
        """Execute pair test

        Args:
            dry_run: If True, skip actual dperf execution and return dummy results
        """
        if dry_run:
            print(f"[Pair {self.pair_index}] [DRY RUN] Skipping actual dperf traffic generation")
            server_cmd = f"sudo ./build/dperf -c config/server_pair{self.pair_index}.conf"
            client_cmd = f"sudo ./build/dperf -c config/client_pair{self.pair_index}.conf"
            print(f"[Pair {self.pair_index}] [DRY RUN] Server command would be: {server_cmd}")
            print(f"[Pair {self.pair_index}] [DRY RUN] Client command would be: {client_cmd}")
            self.serverOutput = None
            self.clientOutput = None
            return {
                'server': None,
                'client': None
            }

        # Create two independent threads to test server and client simultaneously
        serverThread = Thread(target=self.serverStart, name=f"Server-Pair{self.pair_index}")
        clientThread = Thread(target=self.clientStart, name=f"Client-Pair{self.pair_index}")

        print(f"[Pair {self.pair_index}] Starting simultaneous server and client tests...")
        serverThread.start()
        clientThread.start()

        # Wait for both threads to finish
        serverThread.join()
        clientThread.join()

        print(f"[Pair {self.pair_index}] Test completed")
        print(f"[Pair {self.pair_index}] Server output: {self.serverOutput}")
        print(f"[Pair {self.pair_index}] Client output: {self.clientOutput}")

        self.outputResults()

        return {
            'server': self.serverOutput,
            'client': self.clientOutput
        }
        
    def outputResults(self):
        """Output test results to the specified file path."""
        if self.outputPath is None or self.outputPath == "":
            self.outputPath = f"./results/dperf_pair{self.pair_index}_results.csv"

        # Check if the output directory exists, create it if not
        output_dir = os.path.dirname(self.outputPath)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # Try to read data from Redis
        server_data = self.serverOutput
        client_data = self.clientOutput

        if self.enable_redis and self.redis_handler and self.redis_handler.is_connected():
            try:
                # Get server data from Redis
                redis_server = self.get_redis_test_output('server')
                if redis_server and 'metrics' in redis_server:
                    server_data = redis_server['metrics']
                    print(f"[Pair {self.pair_index}] Loaded Server output data from Redis")

                # Get client data from Redis
                redis_client = self.get_redis_test_output('client')
                if redis_client and 'metrics' in redis_client:
                    client_data = redis_client['metrics']
                    print(f"[Pair {self.pair_index}] Loaded Client output data from Redis")
            except Exception as e:
                print(f"[Pair {self.pair_index}] Failed to read data from Redis: {e}, using local data")
            



        # Unit mapping for known dperf metrics
        METRIC_UNITS = {
            'duration':  's',
            # ACK (retransmit / duplicate event counts)
            'ackDup':    'count',
            'ackRt':     'count',
            # ARP
            'arpRx':     'packet',
            'arpTx':     'packet',
            # Bad / Drop / Error
            'badRx':     'packet',
            'dropTx':    'packet',
            'ierrors':   'count',
            'imissed':   'packet',
            'oerrors':   'count',
            # Bits (total transferred)
            'bitsRx':    'bits',
            'bitsTx':    'bits',
            # FIN
            'finRt':     'count',
            'finRx':     'packet',
            'finTx':     'packet',
            # HTTP
            'http2XX':   'count',
            'httpErr':   'count',
            'httpGet':   'count',
            'httpPost':  'count',
            # ICMP
            'icmpRx':    'packet',
            'icmpTx':    'packet',
            # Other packets
            'otherRx':   'packet',
            # Packets
            'pktRx':     'packet',
            'pktTx':     'packet',
            # PUSH
            'pushRt':    'count',
            # RST
            'rstRx':     'packet',
            'rstTx':     'packet',
            # Socket
            'skClose':   'count',
            'skCon':     'count',
            'skErr':     'count',
            'skOpen':    'count',
            # SYN
            'synRt':     'count',
            'synRx':     'packet',
            'synTx':     'packet',
            # TCP
            'tcpDrop':   'packet',
            'tcpRx':     'packet',
            'tcpTx':     'packet',
            # TOS
            'tosRx':     'packet',
            # UDP
            'udpDrop':   'packet',
            'udpRx':     'packet',
            'udpTx':     'packet',
        }

        tg = self.config.test.traffic_generator
        duration_seconds = self._parse_time_to_seconds(tg.duration)

        server_ps = self.serverPerSecond
        client_ps = self.clientPerSecond

        def _safe_max(per_second, key):
            vals = [s[key] for s in per_second if key in s and isinstance(s[key], (int, float))]
            return max(vals) if vals else 'N/A'

        def _derived(total_data, per_second):
            d = {}
            dur = duration_seconds if duration_seconds > 0 else None

            bits_rx = total_data.get('bitsRx') if total_data else None
            pkt_rx  = total_data.get('pktRx')  if total_data else None
            sk_open = total_data.get('skOpen')  if total_data else None

            d['avg_throughput_gbps'] = round(bits_rx / dur / 1e9, 6) if (bits_rx is not None and dur) else 'N/A'
            max_bits = _safe_max(per_second, 'bitsRx')
            d['max_throughput_gbps'] = round(max_bits / 1e9, 6) if isinstance(max_bits, (int, float)) else 'N/A'
            d['avg_throughput_pps']  = round(pkt_rx / dur, 2)              if (pkt_rx  is not None and dur) else 'N/A'
            d['max_throughput_pps']  = _safe_max(per_second, 'pktRx')
            d['avg_cps']             = round(sk_open / dur, 2)             if (sk_open is not None and dur) else 'N/A'
            d['max_cps']             = _safe_max(per_second, 'skOpen')
            d['max_cc']              = _safe_max(per_second, 'skCon')
            return d

        server_derived = _derived(server_data, server_ps)
        client_derived = _derived(client_data, client_ps)

        with open(self.outputPath, 'w') as f:

            # Write CSV
            writer = csv.writer(f)

            # Write header row
            writer.writerow(['Metric', 'Server', 'Client', 'Unit'])
            writer.writerow(['duration',
                             self.config.test.traffic_generator.duration,
                             self.config.test.traffic_generator.duration,
                             's'])

            # Get all possible keys
            all_keys = set()
            if server_data:
                all_keys.update(server_data.keys())
            if client_data:
                all_keys.update(client_data.keys())

            # Write data for each metric
            for key in sorted(all_keys):
                server_value = server_data.get(key, 'N/A') if server_data else 'N/A'
                client_value = client_data.get(key, 'N/A') if client_data else 'N/A'
                unit = METRIC_UNITS.get(key, '')
                writer.writerow([key, server_value, client_value, unit])

            # Write computed derived metrics
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
                writer.writerow([
                    metric,
                    server_derived.get(metric, 'N/A'),
                    client_derived.get(metric, 'N/A'),
                    unit,
                ])


        print(f"[Pair {self.pair_index}] Test results have been exported to {self.outputPath}")

    def serverStart(self):
        def generateServerShell():
            with open(f'shell/server_pair{self.pair_index}.sh', 'w+') as f:
                f.write("cd " + self.config.test.traffic_generator.dperf_path + "\n")
                f.write(f"sudo ./build/dperf -c config/server_pair{self.pair_index}.conf\n")
        """Start dperf server and collect traffic data"""
        try:
            
            generateServerShell()
            
            print(f"[Pair {self.pair_index}] Server: Connecting...")
            # self.server_executor.connect(persistent_session=True)

            print(f"[Pair {self.pair_index}] Server: Changing directory to dperf...")
            self.server_executor.execute_command(
                f"cd {self.config.test.traffic_generator.dperf_path}"
            )

            server_cmd = f"sudo ./build/dperf -c config/server_pair{self.pair_index}.conf"
            print(f"[Pair {self.pair_index}] Server: Executing command -> {server_cmd}")
            # log = self.server_executor.execute_command(server_cmd)
            log = self.server_executor.execute_script(f'shell/server_pair{self.pair_index}.sh')

            print(f"[Pair {self.pair_index}] Server: Parsing output...")
            output = self.parseOutput(log)
            self.serverOutput = output
            self.serverPerSecond = self.parsePerSecondData(log)

            # Write to Redis (if enabled and output data exists)
            if output and self.redis_handler and self.redis_handler.is_connected():
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                success = self.redis_handler.save_test_output(
                    pair_index=self.pair_index,
                    role='server',
                    output=output,
                    timestamp=timestamp
                )
                if success:
                    print(f"[Pair {self.pair_index}] Server: Output data written to Redis")
                else:
                    print(f"[Pair {self.pair_index}] Server: Warning - Failed to write output data to Redis")

            print(f"[Pair {self.pair_index}] Server: Test completed, disconnecting")
            self.server_executor.close()
        except Exception as e:
            print(f"[Pair {self.pair_index}] Server execution failed: {e}")
            self.serverOutput = None
        finally:
            os.remove(f'shell/server_pair{self.pair_index}.sh')

    def clientStart(self):
        """Start dperf client and collect traffic data"""
        def generateClientShell():
            with open(f'shell/client_pair{self.pair_index}.sh', 'w+') as f:
                f.write("cd " + self.config.test.traffic_generator.dperf_path + "\n")
                f.write(f"sudo ./build/dperf -c config/client_pair{self.pair_index}.conf\n")
        try:
            generateClientShell()
            print(f"[Pair {self.pair_index}] Client: Connecting...")
            # self.client_executor.connect(persistent_session=True)

            print(f"[Pair {self.pair_index}] Client: Changing directory to dperf...")
            self.client_executor.execute_command(
                f"cd {self.config.test.traffic_generator.dperf_path}"
            )

            client_cmd = f"sudo ./build/dperf -c config/client_pair{self.pair_index}.conf"
            print(f"[Pair {self.pair_index}] Client: Executing command -> {client_cmd}")
            # log = self.client_executor.execute_command(client_cmd)
            log = self.client_executor.execute_script(f'shell/client_pair{self.pair_index}.sh')
            print(f"[Pair {self.pair_index}] Client: Parsing output...")
            output = self.parseOutput(log)
            self.clientOutput = output
            self.clientPerSecond = self.parsePerSecondData(log)

            # Write to Redis (if enabled and output data exists)
            if output and self.redis_handler and self.redis_handler.is_connected():
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                success = self.redis_handler.save_test_output(
                    pair_index=self.pair_index,
                    role='client',
                    output=output,
                    timestamp=timestamp
                )
                if success:
                    print(f"[Pair {self.pair_index}] Client: Output data written to Redis")
                else:
                    print(f"[Pair {self.pair_index}] Client: Warning - Failed to write output data to Redis")

            print(f"[Pair {self.pair_index}] Client: Test completed, disconnecting")
            self.client_executor.close()
        except Exception as e:
            print(f"[Pair {self.pair_index}] Client execution failed: {e}")
            self.clientOutput = None
        finally:
            os.remove(f'shell/client_pair{self.pair_index}.sh')

    

    def parsePerSecondData(self, log):
        """解析 log 中每秒區塊資料，回傳 list of dict（不含 Total Numbers 之後的資料）"""
        raw = log[0]
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
        raw = ansi_escape.sub('', raw)

        # 只取 Total Numbers 之前的部分
        total_idx = raw.find("Total Numbers")
        if total_idx != -1:
            raw = raw[:total_idx]

        per_second = []
        # 找每個 "seconds X" 區塊的起始位置
        import re as _re
        block_starts = [m.start() for m in _re.finditer(r'(?m)^seconds\s+\d+', raw)]

        for i, start in enumerate(block_starts):
            end = block_starts[i + 1] if i + 1 < len(block_starts) else len(raw)
            block = raw[start:end].strip()
            block_dict = {}
            for line in block.split('\n'):
                parts = line.split()
                j = 0
                while j + 1 < len(parts):
                    key = parts[j]
                    val = parts[j + 1]
                    try:
                        block_dict[key] = int(val.replace(',', ''))
                    except ValueError:
                        block_dict[key] = val
                    j += 2
            if block_dict:
                per_second.append(block_dict)

        return per_second

    def parseOutput(self, log):
        log = log[0]

        # Remove ANSI escape sequences (color codes)
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
        log = ansi_escape.sub('', log)

        # Find "dperf Test Finished" string and extract content after it
        if "dperf Test Finished" in log:
            index = log.find("Total Numbers")
            result = log[index:].strip()

            # Parse stats into dict
            stats_dict = {}
            lines = result.split("\n")

            for line in lines[1:]:  # Skip first line "Total Numbers:"
                line = line.strip()
                if not line:
                    continue

                # Split each line's statistical items
                parts = line.split()
                i = 0
                while i < len(parts):
                    # Each item is a key-value pair
                    if i + 1 < len(parts):
                        key = parts[i]
                        value = parts[i + 1]

                        # Remove commas from numbers and convert to integer
                        try:
                            value_clean = value.replace(",", "")
                            stats_dict[key] = int(value_clean)
                        except ValueError:
                            # If conversion to int fails, keep original string
                            stats_dict[key] = value

                        i += 2
                    else:
                        i += 1

            # print(result)
            # print("Statistics (dict format):")
            # print(stats_dict)
            return stats_dict
        else:
            print("String 'dperf Test Finished' not found")
            return None

    def bindNICs(self):
        """Bind NICs to DPDK driver"""
        try:
            self.executor.execute_command(
                f"cd {self.config.test.traffic_generator.dpdk_path}/usertools"
            )
            self.executor.execute_command(
                f"nmcli connection down {self.pair.client.client_nic_name}"
            )
            self.executor.execute_command(
                f"nmcli connection down {self.pair.server.server_nic_name}"
            )
            self.executor.execute_command(
                f"sudo python3 dpdk-devbind.py -b vfio-pci {self.pair.client.client_nic_pci} --noiommu-mode"
            )
            self.executor.execute_command(
                f"sudo python3 dpdk-devbind.py -b vfio-pci {self.pair.server.server_nic_pci} --noiommu-mode"
            )

        except Exception as e:
            raise Exception(f"Failed to bind NIC: {e}")

    def unbindNICs(self):
        """Unbind NICs from DPDK driver and restore original driver"""
        try:
            self.executor.execute_command(
                f"cd {self.config.test.traffic_generator.dpdk_path}/usertools"
            )
            # Bind NIC back to original driver
            self.executor.execute_command(
                f"sudo python3 dpdk-devbind.py -b {self.pair.client.client_nic_driver} {self.pair.client.client_nic_pci}"
            )
            self.executor.execute_command(
                f"sudo python3 dpdk-devbind.py -b {self.pair.server.server_nic_driver} {self.pair.server.server_nic_pci}"
            )
            # Restart network connection
            self.executor.execute_command(
                f"nmcli connection up {self.pair.client.client_nic_name}"
            )
            self.executor.execute_command(
                f"nmcli connection up {self.pair.server.server_nic_name}"
            )
            # Display status
            self.executor.execute_command("sudo python3 dpdk-devbind.py --status")

        except Exception as e:
            raise Exception(f"Failed to unbind NIC: {e}")
        
    def setHugePages(self):
        """Set up hugepages

        Args:
            pages: number of hugepages
            size: hugepage size (1G or 2M)
        """
        pages = self.config.test.traffic_generator.hugepage_frames
        size = self.config.test.traffic_generator.hugepage_size

        try:
            self.executor.execute_command(
                f"cd {self.config.test.traffic_generator.dpdk_path}/usertools"
            )
            total_mem = f"{pages * int(size[:-1])}{size[-1]}"
            self.executor.execute_command(
                f"sudo python3 dpdk-hugepages.py -p {size} --setup {total_mem}"
            )
        except Exception as e:
            print(f"Failed to set hugepages: {e}")
            raise
    
    def clearHugePages(self):
        try:
            self.executor.execute_command(
                f"cd {self.config.test.traffic_generator.dpdk_path}/usertools"
            )
            self.executor.execute_command(
                "sudo python3 dpdk-hugepages.py --clear"
            )
        except Exception as e:
            print(f'Fail to clear HugePages {e}')
            raise

    def setupConfig(self):
        """Create dperf configuration files"""
        print("=============Creating dperf configuration files=============")
        with open(f"config/server_pair{self.pair_index}.conf", 'w') as f:
            f.write(self.generateServerConfig())
        with open(f"config/client_pair{self.pair_index}.conf", 'w') as f:
            f.write(self.generateClientConfig())
        self.executor.execute_command(
            f"cd {self.config.test.traffic_generator.dperf_path}"
        )
        self.executor.execute_command("mkdir -p config")
        serverConfig = self.generateServerConfig()
        clientConfig = self.generateClientConfig()
        self.executor.execute_command(
            f"cat > config/server_pair{self.pair_index}.conf << 'EOF'\n{serverConfig}\nEOF"
        )
        self.executor.execute_command(
            f"cat > config/client_pair{self.pair_index}.conf << 'EOF'\n{clientConfig}\nEOF"
        )
        self.executor.execute_command("ls -l config/")

    def setupEnv(self, dry_run=False):
        """Set up dperf environment"""
        if dry_run:
            tg = self.config.test.traffic_generator
            print(f"[Pair {self.pair_index}] [DRY RUN] Would set hugepages: {tg.hugepage_frames}x{tg.hugepage_size}")
            print(f"[Pair {self.pair_index}] [DRY RUN] Would bind NICs (vfio-pci): {self.pair.client.client_nic_pci}, {self.pair.server.server_nic_pci}")
            print(f"[Pair {self.pair_index}] [DRY RUN] Server config (config/server_pair{self.pair_index}.conf):\n{self.generateServerConfig()}")
            print(f"[Pair {self.pair_index}] [DRY RUN] Client config (config/client_pair{self.pair_index}.conf):\n{self.generateClientConfig()}")
            return

        try:
            # Set up hugepages
            self.setHugePages()
            # Bind NICs
            self.bindNICs()
            # Create configuration files
            self.setupConfig()

        except Exception as e:
            print(f"Failed to set up dperf environment: {e}")
            raise

    def clearEnv(self, dry_run=False):
        if dry_run:
            print(f"[Pair {self.pair_index}] [DRY RUN] Would clear hugepages and unbind NICs: {self.pair.client.client_nic_pci}, {self.pair.server.server_nic_pci}")
            return

        try:
            # clear hugepages setting
            self.clearHugePages()

            # unbind nic
            self.unbindNICs()
        except Exception as e:
            print(f"Fail to clear dperf env: {e}")
            raise

    def get_redis_summary(self):
        """Get pair data summary from Redis"""
        if self.redis_handler and self.redis_handler.is_connected():
            summary = self.redis_handler.get_pair_summary(self.pair_index)
            return summary
        else:
            return None

    def get_redis_test_output(self, role):
        """Get test output data (server or client) from Redis"""
        if self.redis_handler and self.redis_handler.is_connected():
            return self.redis_handler.get_test_output(self.pair_index, role)
        else:
            return None

    def get_redis_monitor_data(self):
        """Get monitor data from Redis"""
        if self.redis_handler and self.redis_handler.is_connected():
            return self.redis_handler.get_monitor_data(self.pair_index)
        return None


# def argParser():
#     import argparse

#     parser = argparse.ArgumentParser(description="dperf Test Settings")
#     parser.add_argument('--config', type=str, default='config.yaml', help='Path to configuration file')
#     parser.add_argument('--pair_index', type=int, default=0, help='Index of pair to test')
#     parser.add_argument('--enable_redis', action='store_true', help='Whether to enable Redis for testing data storage')
#     return parser.parse_args()


# if __name__ == "__main__":
#     args= argParser()
#     # Load configuration file
#     config = Config()
#     config.from_yaml(args.config)

#     # Create dperf instance, enable Redis
#     test = dperf(config=config, pair_index=args.pair_index, enable_redis=args.enable_redis)
#     # Connect to remote host
#     test.connect()

#     # Set up environment
#     test.setupEnv()

#     # Execute test
#     output = test.runPairTest()

#     print("\n" + "="*60)
#     print("Test Output:")
#     print("="*60)
#     print(output)

#     # If Redis is enabled, display summary of data in Redis
#     if test.redis_handler and test.redis_handler.is_connected():
#         print("\n" + "="*60)
#         print("Redis Data Summary:")
#         print("="*60)
#         summary = test.get_redis_summary()
#         if summary:
#             print(f"Pair Index: {summary['pair_index']}")
#             print(f"Monitor Data Count: {summary['monitor_count']}")
#             print(f"Server Output Count: {summary['server_output_count']}")
#             print(f"Client Output Count: {summary['client_output_count']}")

#         # Display latest server and client output
#         print("\n" + "="*60)
#         print("Latest Test Output in Redis:")
#         print("="*60)

#         server_data = test.get_redis_test_output('server')
#         if server_data:
#             print(f"\nServer Output (Time: {server_data.get('timestamp')}):")
#             for key, value in server_data.items():
#                 if key not in ['pair_index', 'role', 'timestamp']:
#                     print(f"  {key}: {value}")

#         client_data = test.get_redis_test_output('client')
#         if client_data:
#             print(f"\nClient Output (Time: {client_data.get('timestamp')}):")
#             for key, value in client_data.items():
#                 if key not in ['pair_index', 'role', 'timestamp']:
#                     print(f"  {key}: {value}")

#    # Disconnect
#     test.disconnect()
    
    
    
    