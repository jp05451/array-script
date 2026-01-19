import ssh_executor
from config import Config


class APVSetup:
    def __init__(self, config: Config,log_path: str = 'logs'):
        self.apv_management_ip = config.test.apv_management_ip
        self.apv_management_port: int = config.test.apv_management_port
        self.apv_username: str = config.test.apv_username
        self.apv_password: str = config.test.apv_password
        self.apv_enable_password: str = config.test.apv_enable_password
        self.pairs = config.test.traffic_generator.pairs
        self.ssh_apv = ssh_executor.SSHExecutor(
            host=self.apv_management_ip,
            port=self.apv_management_port,
            user=self.apv_username,
            password=self.apv_password,
            log_path=f'{log_path}/apv.log',            
        )
    
    def _execute_commands(self, commands: list, dry_run: bool = False):
        """執行指令陣列，根據 dry_run 模式決定是列印還是執行"""
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
                "no slb virtual udp udp_slb_vs",
                "no slb group method udp_slb_rs_group",
            ]
        else:
            # Setup commands - full parameters
            commands = [
                # configure UDP real servers
                f"slb real udp udp_rs_{pair_index} {self.pairs[pair_index].server.server_ip} {self.pairs[pair_index].server.listen_port} 0 3 3 60 none",
                f"slb real enable udp_rs_{pair_index}",
                
                # configure UDP virtual server
                f'slb virtual udp udp_slb_vs {self.pairs[pair_index].client.virtual_server_ip} {self.pairs[pair_index].client.virtual_server_port}',
                'slb virtual enable udp_slb_vs',
                
                # configure UDP load balancer group
                'slb group method udp_slb_rs_group rr',
                f'slb group member udp_slb_rs_group udp_rs_{pair_index}',
                'slb group enable udp_slb_rs_group',
                
                # configure UDP virtual server policy
                'slb policy default udp_slb_vs udp_slb_rs_group'
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
                "no slb virtual tcp tcp_slb_vs",
                "no slb group method tcp_slb_rs_group",
            ]
        else:
            # Setup commands - full parameters
            commands = [
                # setup TCP real servers
                f"slb real tcp tcp_rs_{pair_index} {self.pairs[pair_index].server.server_ip} {self.pairs[pair_index].server.listen_port} 0 none",
                f"slb real enable tcp_rs_{pair_index}",
                # configure TCP virtual server
                f'slb virtual tcp tcp_slb_vs {self.pairs[pair_index].client.virtual_server_ip} {self.pairs[pair_index].client.virtual_server_port}',
                'slb virtual enable tcp_slb_vs',
                # configure TCP load balancer group
                'slb group method tcp_slb_rs_group rr',
                f'slb group member tcp_slb_rs_group tcp_rs_{pair_index}',
                'slb group enable tcp_slb_rs_group',
                # configure TCP virtual server policy
                'slb policy default tcp_slb_vs tcp_slb_rs_group'
            ]

        if dry_run:
            action = "Cleaning up" if clear else "Setting up"
            print(f"Dry run: {action} TCP Load Balancer for pair index {pair_index}")

        self._execute_commands(commands, dry_run)
        
    def setupHTTPLoadBalancer(self, pair_index, dry_run=False, clear=False):
        if clear:
            # Clean up commands - minimal parameters only
            commands = [
                f"no slb real http http_rs_{pair_index}",
                "no slb virtual http http_slb_vs",
                "no slb group method http_slb_rs_group",
            ]
        else:
            # Setup commands - full parameters
            commands = [
                # setup HTTP real servers
                f"slb real http http_rs_{pair_index} {self.pairs[pair_index].server.server_ip} {self.pairs[pair_index].server.listen_port} 0 none",
                f"slb real enable http_rs_{pair_index}",
                # configure HTTP virtual server
                f'slb virtual http http_slb_vs {self.pairs[pair_index].client.virtual_server_ip} {self.pairs[pair_index].client.virtual_server_port}',
                'slb virtual enable http_slb_vs',
                # configure HTTP load balancer group
                'slb group method http_slb_rs_group rr',
                f'slb group member http_slb_rs_group http_rs_{pair_index}',
                'slb group enable http_slb_rs_group',
                # configure HTTP virtual server policy
                'slb policy default http_slb_vs http_slb_rs_group'
            ]

        if dry_run:
            action = "Cleaning up" if clear else "Setting up"
            print(f"Dry run: {action} HTTP Load Balancer for pair index {pair_index}")

        self._execute_commands(commands, dry_run)
        
    
    def setupEnv(self, dry_run=False, clear=False):
        self.ssh_apv.execute_command('enable',real_time=True)
        self.ssh_apv.execute_command(f'{self.apv_enable_password}',real_time=True)
        
        self.ssh_apv.execute_command('config terminal',real_time=True)
        for i in range(len(self.pairs)):
            protocol = self.pairs[i].protocol.lower()
            if protocol == 'udp':
                print('UDP')
                self.setupUDPLoadBalancer(pair_index=i,dry_run=dry_run,clear=clear)
            elif protocol == 'tcp':
                print('TCP')
                self.setupTCPLoadBalancer(pair_index=i,dry_run=dry_run,clear=clear)
            elif protocol == 'http':
                print('HTTP')
                self.setupHTTPLoadBalancer(pair_index=i,dry_run=dry_run,clear=clear)
            else:
                raise ValueError(f"Unsupported protocol: {protocol}")
        if not dry_run:
            self.ssh_apv.execute_command('write memory',real_time=True)
    
    def connect(self):
        self.ssh_apv.connect(persistent_session=True,)
        
    def disconnect(self):
        self.ssh_apv.close()
        
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
    apv_setup.setupEnv(dry_run=args.dry_run, clear=args.clear)
    apv_setup.disconnect()
