import ssh_executor
from config import Config
from output_handler import OutputHandler
import csv
import os
import re


class APVSetup:
    def __init__(self, config: Config,log_path: str = 'logs'):
        self.logPath = log_path
        self.apv_management_ip = config.test.apv_management_ip
        self.apv_management_port: int = config.test.apv_management_port
        self.apv_username: str = config.test.apv_username
        self.apv_password: str = config.test.apv_password
        self.apv_enable_password: str = config.test.apv_enable_password
        self.pairs = config.test.traffic_generator.pairs
        self.per_pair_slb: dict = {}
        self.ssh_apv = ssh_executor.SSHExecutor(
            host=self.apv_management_ip,
            port=self.apv_management_port,
            user=self.apv_username,
            password=self.apv_password,
            log_path=f'{log_path}/apv.log',            
        )
    
    def __del__(self):
        """Destructor to automatically disconnect from the server"""
        try:
            self.disconnect()
        except:
            pass
    
    def _execute_commands(self, commands: list, dry_run: bool = False):
        """Execute a list of commands, either printing them or executing them based on dry_run mode"""
        if dry_run:
            for cmd in commands:
                print(cmd)
        else:
            for cmd in commands:
                self.ssh_apv.execute_command(cmd)

    def setupUDPLoadBalancer(self, pair_index, dry_run=False, clear=False):
        if clear:
            # Clean up commands - minimal parameters only
            commands = [
                f"no slb real udp udp_rs_{pair_index}",
                f"no slb virtual udp udp_vs_{pair_index}",
                "no slb group method udp_slb_rs_group",
            ]
        else:
            # Setup commands - full parameters
            commands = [
                # configure UDP real servers
                f"slb real udp udp_rs_{pair_index} {self.pairs[pair_index].server.server_ip} {self.pairs[pair_index].server.listen_port} 0 3 3 60 none",
                f"slb real enable udp_rs_{pair_index}",
                
                # configure UDP virtual server
                f'slb virtual udp udp_vs_{pair_index} {self.pairs[pair_index].client.virtual_server_ip} {self.pairs[pair_index].client.virtual_server_port}',
                f'slb virtual enable udp_vs_{pair_index}',
                
                # configure UDP load balancer group
                'slb group method udp_slb_rs_group rr',
                f'slb group member udp_slb_rs_group udp_rs_{pair_index}',
                'slb group enable udp_slb_rs_group',
                
                # configure UDP virtual server policy
                f'slb policy default udp_vs_{pair_index} udp_slb_rs_group'
            ]

        if dry_run:
            action = "Cleaning up" if clear else "Setting up"
            print(f"Dry run: {action} UDP Load Balancer for pair index {pair_index}")

        self._execute_commands(commands, dry_run)

        
    def setupTCPLoadBalancer(self, pair_index, dry_run=False, clear=False):
        if clear:
            # Clean up commands - minimal parameters only
            commands = [
                f"no slb real tcp tcp_rs_{pair_index}",
                f"no slb virtual tcp tcp_vs_{pair_index}",
                "no slb group method tcp_slb_rs_group",
            ]
            if dry_run:
                print(f"Dry run: Cleaning up TCP Load Balancer for pair index {pair_index}")

            self._execute_commands(commands, dry_run)
            return
        
        # Setup commands - full parameters
        commands = [
            # setup TCP real servers
            f"slb real tcp tcp_rs_{pair_index} {self.pairs[pair_index].server.server_ip} {self.pairs[pair_index].server.listen_port} 0 none",
            f"slb real enable tcp_rs_{pair_index}",
            
            # configure TCP virtual server
            f'slb virtual tcp tcp_vs_{pair_index} {self.pairs[pair_index].client.virtual_server_ip} {self.pairs[pair_index].client.virtual_server_port}',
            f'slb virtual enable tcp_vs_{pair_index}',
            
            # configure TCP load balancer group
            'slb group method tcp_slb_rs_group rr',
            f'slb group member tcp_slb_rs_group tcp_rs_{pair_index}',
            'slb group enable tcp_slb_rs_group',
            
            # configure TCP virtual server policy
            f'slb policy default tcp_vs_{pair_index} tcp_slb_rs_group'
        ]

        if dry_run:
            print(f"Dry run: Setting up TCP Load Balancer for pair index {pair_index}")

        self._execute_commands(commands, dry_run)

        
    def setupHTTPLoadBalancer(self, pair_index, dry_run=False,clear=False):
        if clear:
            # Clean up commands - minimal parameters only
            commands = [
                f"no slb real http http_rs_{pair_index}",
                f"no slb virtual http http_vs_{pair_index}",
                "no slb group method http_slb_rs_group",
            ]
            if dry_run:
                print(f"Dry run: Cleaning up HTTP Load Balancer for pair index {pair_index}")

            self._execute_commands(commands, dry_run)
            return
    
        # Setup commands - full parameters
        commands = [
            # setup HTTP real servers
            f"slb real http http_rs_{pair_index} {self.pairs[pair_index].server.server_ip} {self.pairs[pair_index].server.listen_port} 0 none",
            f"slb real enable http_rs_{pair_index}",
            
            # configure HTTP virtual server
            f'slb virtual http http_vs_{pair_index} {self.pairs[pair_index].client.virtual_server_ip} {self.pairs[pair_index].client.virtual_server_port}',
            f'slb virtual enable http_vs_{pair_index}',
            
            # configure HTTP load balancer group
            'slb group method http_slb_rs_group rr',
            f'slb group member http_slb_rs_group http_rs_{pair_index}',
            'slb group enable http_slb_rs_group',
            
            # configure HTTP virtual server policy
            f'slb policy default http_vs_{pair_index} http_slb_rs_group'
        ]

        if dry_run:
            print(f"Dry run: Setting up HTTP Load Balancer for pair index {pair_index}")
        self._execute_commands(commands, dry_run)
        
    
    def setupEnv(self, dry_run=False):
        if dry_run:
            print(f"[APVSetup] [DRY RUN] APV: {self.apv_management_ip}:{self.apv_management_port} (user: {self.apv_username})")
        else:
            self.ssh_apv.execute_command('enable')
            self.ssh_apv.execute_command(f'{self.apv_enable_password}')
            self.ssh_apv.execute_command('config terminal')

        self.ssh_apv.execute_command('no pager')
        for i in range(len(self.pairs)):
            protocol = self.pairs[i].protocol.lower()
            if protocol == 'udp':
                print("Setting up UDP")
                self.setupUDPLoadBalancer(pair_index=i,dry_run=dry_run,clear=False)
            elif protocol == 'tcp':
                print("Setting up TCP")
                self.setupTCPLoadBalancer(pair_index=i,dry_run=dry_run,clear=False)
            elif protocol == 'http':
                print("Setting up HTTP")
                self.setupHTTPLoadBalancer(pair_index=i,dry_run=dry_run,clear=False)
            else:
                raise ValueError(f"Unsupported protocol: {protocol}")

        if not dry_run:
            self.ssh_apv.execute_command('write memory',real_time=True)

    def clearEnv(self, dry_run=False):
        if dry_run:
            print(f"[APVSetup] [DRY RUN] Would clear APV config on {self.apv_management_ip}")
            return

        self.ssh_apv.execute_command('enable',real_time=True)
        self.ssh_apv.execute_command(f'{self.apv_enable_password}',real_time=True)
        self.ssh_apv.execute_command('config terminal',real_time=True)
        for i in range(len(self.pairs)):
            protocol = self.pairs[i].protocol.lower()
            if protocol == 'udp':
                print('Clearing UDP')
                self.setupUDPLoadBalancer(pair_index=i,dry_run=dry_run,clear=True)
            elif protocol == 'tcp':
                print('Clearing TCP')
                self.setupTCPLoadBalancer(pair_index=i,dry_run=dry_run,clear=True)
            elif protocol == 'http':
                print('Clearing HTTP')
                self.setupHTTPLoadBalancer(pair_index=i,dry_run=dry_run,clear=True)
            else:
                raise ValueError(f"Unsupported protocol: {protocol}")
        self.ssh_apv.execute_command('write memory',real_time=True)
    
    def connect(self):
        self.ssh_apv.connect(persistent_session=True,keepalive_interval=30)

    def disconnect(self):
        self.ssh_apv.close()

    # -------------------------------------------------------------------------
    # SLB Statistics Collection
    # -------------------------------------------------------------------------

    def collectSLBStats(self) -> str:
        """Run 'show statistics slb all' after entering enable mode and return complete raw output string.

        APV paginates output with "--More--", continue sending 'c' until full content is obtained.
        After execution, send 'exit' to return to user mode to ensure subsequent clearEnv enable flow is not affected.
        Raw output is also written to <logPath>/apv_slb_raw.log for debugging.
        """
        shell = self.ssh_apv._executor
        assert shell is not None, "APV SSH session not established; call connect() first"
        shell.execute_in_session('enable', timeout=15)
        shell.execute_in_session(self.apv_enable_password, timeout=15)

        # Collect full output: Continue sending Enter('\n') when APV paginates until prompt (AN#) is seen
        full_output = shell.execute_in_session('show statistics slb all', timeout=30)
        while '--More--' in full_output and not re.search(r'AN[^\n]*#\s*$', full_output):
            page = shell.execute_in_session('\n', timeout=30)
            full_output += '\n' + page
            if re.search(r'AN[^\n]*#\s*$', page):
                break

        shell.execute_in_session('disable', timeout=10)   # Return to user mode (do not close session)

        # Write debug log (remove backspace and --More-- before saving)
        debug_log = os.path.join(self.logPath, 'apv_slb_raw.log')
        try:
            clean_log = OutputHandler.clean_ansi(full_output)
            clean_log = re.sub(r'\x08+', '', clean_log)
            clean_log = re.sub(r'[ \t]*--More--[ \t]*\n?', '', clean_log)
            with open(debug_log, 'w') as f:
                f.write(clean_log)
        except Exception:
            pass

        return full_output

    @staticmethod
    def parseSLBStats(raw: str) -> dict:
        """Parse raw output of 'show statistics slb all'.

        Return structure:
            {
              'vs': [{'ip': str, 'metrics': {field: value}}, ...],
              'rs': [{'name': str, 'ip': str, 'port': str, 'status': str,
                      'metrics': {field: value}}, ...],
            }
        """
        # Remove ANSI control codes, \r, backspace (\x08) and --More-- artifacts
        clean = OutputHandler.clean_ansi(raw)
        clean = re.sub(r'\x08+', '', clean)
        clean = re.sub(r'[ \t]*--More--[ \t]*', '', clean)

        result = {'vs': [], 'rs': []}

        # ── Parse RS Blocks ──────────────────────────────────────────────────────────
        # Header format: Real service <name> <ip> <port> <state...>
        rs_header = re.compile(
            r'^Real service\s+(\S+)\s+([\d.]+)\s+(\d+)\s+(.+)', re.MULTILINE
        )
        rs_splits = list(rs_header.finditer(clean))
        for idx, m in enumerate(rs_splits):
            block_start = m.end()
            block_end   = rs_splits[idx + 1].start() if idx + 1 < len(rs_splits) else len(clean)
            block_text  = clean[block_start:block_end]

            metrics = APVSetup._parse_kv_block(block_text)
            metrics.pop('First hit after RS active', None)
            result['rs'].append({
                'name':    m.group(1),
                'ip':      m.group(2),
                'port':    m.group(3),
                'status':  m.group(4).strip(),
                'metrics': metrics,
            })

        # ── Parse VS Blocks ──────────────────────────────────────────────────────────
        # Header format: <protocol> virtual service "<name>" (<ip> <port>) <state>
        # Example: tcp virtual service "tcp_slb_vs" (10.10.11.101 6769) UP
        vs_header = re.compile(
            r'^\s*\w+\s+virtual service\s+"([^"]+)"\s+\(([\d.]+)\s+(\d+)\)\s+(\S+)',
            re.MULTILINE
        )
        vs_splits = list(vs_header.finditer(clean))
        for idx, m in enumerate(vs_splits):
            block_start = m.end()
            next_vs   = vs_splits[idx + 1].start() if idx + 1 < len(vs_splits) else len(clean)
            block_end = next_vs
            block_text = clean[block_start:block_end]

            metrics = APVSetup._parse_kv_block(block_text)
            result['vs'].append({
                'name':   m.group(1),
                'ip':     m.group(2),
                'port':   m.group(3),
                'status': m.group(4),
                'metrics': metrics,
            })

        return result

    @staticmethod
    def _parse_kv_block(text: str) -> dict:
        """Extract all 'Key: value [unit]' pairs from a block of text and return dict."""
        metrics = {}
        for line in text.splitlines():
            # Match "    Some Key Label:   123" or "    Key:  0.000 ms"
            m = re.match(r'^\s+(.+?):\s+(.+?)\s*$', line)
            if not m:
                continue
            key = m.group(1).strip()
            val = m.group(2).strip()
            # Try to convert to numeric (remove units bps/pps/ms)
            num_match = re.match(r'^([\d.]+)\s*(?:bps|pps|ms)?$', val)
            if num_match:
                raw_num = num_match.group(1)
                metrics[key] = float(raw_num) if '.' in raw_num else int(raw_num)
            else:
                metrics[key] = val
        return metrics

    # Metric unit mapping table
    _SLB_METRIC_UNITS = {
        # Connection count / Requests
        'Max Conn Count':             'count',
        'Max Connection Count':       'count',
        'Current Connection Count':   'count',
        'Current CPS Count':          'cps',
        'Outstanding Request Count':  'count',
        'Total Hits':                 'count',
        'Total Connection Count':     'count',
        # Traffic (bytes)
        'Total Bytes In':             'bytes',
        'Total Bytes Out':            'bytes',
        # Packet count
        'Total Packets In':           'packet',
        'Total Packets Out':          'packet',
        # Bandwidth
        'Average Bandwidth In':       'bps',
        'Average Bandwidth Out':      'bps',
        # Packet rate
        'Average Packets In Rate':    'pps',
        'Average Packets Out Rate':   'pps',
        # Latency
        'Average Response time':      'ms',
        'Average client connection RTT': 'ms',
        # QoS / Policy hits
        'qos clientport hits':        'count',
        'qos network hits':           'count',
        'default hits':               'count',
        'doh hits':                   'count',
        'static hits':                'count',
        'backup hits':                'count',
    }

    def resolvePortNames(self) -> None:
        """Run 'show ip address' to parse APV port name and fill apv_client_port / apv_server_port for each pair.

        Use execute_in_session (enable mode), no need for additional connect/disconnect.
        Fill 'unknown' if corresponding IP not found.
        """
        shell = self.ssh_apv._executor
        assert shell is not None, "APV SSH session not established; call connect() first"

        shell.execute_in_session('enable', timeout=15)
        shell.execute_in_session(self.apv_enable_password, timeout=15)
        raw = shell.execute_in_session('show ip address', timeout=15)
        shell.execute_in_session('disable', timeout=10)

        # Parse: ip address "portX" <ip> <mask>
        clean = OutputHandler.clean_ansi(raw)
        clean = re.sub(r'\x08+', '', clean)
        ip_map: dict[str, str] = {}
        for line in clean.splitlines():
            m = re.match(r'\s*ip address\s+"([^"]+)"\s+([\d.]+)', line)
            if m:
                ip_map[m.group(2)] = m.group(1)

        for pair in self.pairs:
            pair.apv_client_port = ip_map.get(pair.client.client_gw, 'unknown')
            pair.apv_server_port = ip_map.get(pair.server.server_gw, 'unknown')

    def matchSLBStatsToPairs(self, parsed: dict) -> dict:
        """Group VS/RS from parseSLBStats return by pair_index in their names.

        Return: {pair_index: {'vs': vs_entry_or_None, 'rs': rs_entry_or_None}}
        VS name format: {protocol}_vs_{pair_index} (e.g., tcp_vs_0)
        RS name format: {protocol}_rs_{pair_index} (e.g., tcp_rs_0)
        """
        per_pair = {i: {'vs': None, 'rs': None} for i in range(len(self.pairs))}

        for vs in parsed.get('vs', []):
            m = re.search(r'_vs_(\d+)$', vs['name'])
            if m:
                idx = int(m.group(1))
                if idx in per_pair:
                    per_pair[idx]['vs'] = vs

        for rs in parsed.get('rs', []):
            m = re.search(r'_rs_(\d+)$', rs['name'])
            if m:
                idx = int(m.group(1))
                if idx in per_pair:
                    per_pair[idx]['rs'] = rs

        return per_pair

    def outputSLBStats(self, parsed: dict, per_pair_slb: dict, output_path: str):
        """Write parsed SLB statistics to CSV.

        Output file: <output_path>/apv_slb_stats.csv
        Columns: Type, Pair, Metric, Value, Unit
        """
        os.makedirs(output_path, exist_ok=True)
        csv_path = os.path.join(output_path, 'apv_slb_stats.csv')

        # Build reverse lookup table: identifier → pair_label
        id_to_pair: dict[str, str] = {}
        for pair_idx, slb in per_pair_slb.items():
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
                unit = self._SLB_METRIC_UNITS.get(metric, '')
                rows.append(['VS', pair_label, metric, value, unit])

        for rs in parsed.get('rs', []):
            identifier = f"{rs['name']} ({rs['ip']}:{rs['port']}) [{rs['status']}]"
            pair_label = id_to_pair.get(identifier, '-')
            for metric, value in rs['metrics'].items():
                unit = self._SLB_METRIC_UNITS.get(metric, '')
                rows.append(['RS', pair_label, metric, value, unit])

        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Type', 'Pair', 'Metric', 'Value', 'Unit'])
            writer.writerows(rows)

        print(f"[APVSetup] SLB statistics output to {csv_path}")

    def collectAndProcessSLBStats(self, output_path: str) -> None:
        """Collect, parse, group and output SLB statistics, store result in self.per_pair_slb."""
        raw = self.collectSLBStats()
        parsed = self.parseSLBStats(raw)
        self.per_pair_slb = self.matchSLBStatsToPairs(parsed)
        self.outputSLBStats(parsed, self.per_pair_slb, output_path)

def argParser():
    import argparse

    parser = argparse.ArgumentParser(description="APV Load Balancer Setup Script")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Run the setup in dry-run mode without making changes",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        default=False,
        help="Clear load balancer settings by adding 'no' prefix to commands",
    )
    parser.add_argument(
        '-c', '--config',
        type=str,
        default="config.yaml",
        help="Path to the configuration YAML file"
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = argParser()
    config = Config()
    config.from_yaml(args.config)
    apv_setup = APVSetup(config)
    apv_setup.connect()
    if args.clear:
        apv_setup.clearEnv(dry_run=args.dry_run)
    else:
        apv_setup.setupEnv(dry_run=args.dry_run)
    apv_setup.disconnect()
