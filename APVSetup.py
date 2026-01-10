import ssh_executor
from config import Config


class APVSetup:
    def __init__(self, config: Config):
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
            # log_path='logs/apv_setup.log',            
        )
    
    def setupUDPLoadBalancer(self,pair_index,dry_run=False):
        if dry_run:
            print(f"Dry run: Setting up UDP Load Balancer for pair index {pair_index}")
            print(f"slb real udp udp_rs_{pair_index} {self.pairs[pair_index].server.server_ip} {self.pairs[pair_index].server.listen_port}")
            
            # configure UDP load balancer group
            print('slb group method udp_slb_rs_group rr')
            
            print(f'slb group member udp_slb_rs_group udp_rs_{pair_index}')
            print('slb group enable udp_slb_rs_group')
            
            # configure UDP virtual server
            print(f'slb virtual udp udp_slb_vs {self.pairs[pair_index].client.virtual_server_ip} {self.pairs[pair_index].client.virtual_server_port}')
            print('slb virtual enable udp_slb_vs')
            print('slb policy default udp_slb_vs udp_slb_rs_group')
            
        else:
            # configure UDP real servers
            self.ssh_apv.execute_command(f"slb real udp udp_rs_{pair_index} {self.pairs[pair_index].server.server_ip} {self.pairs[pair_index].server.listen_port}")
            
            # configure UDP load balancer group
            self.ssh_apv.execute_command('slb group method udp_slb_rs_group rr')
            
            self.ssh_apv.execute_command(f'slb group member udp_slb_rs_group udp_rs_{pair_index}')
            self.ssh_apv.execute_command('slb group enable udp_slb_rs_group')
            
            # configure UDP virtual server
            self.ssh_apv.execute_command(f'slb virtual udp udp_slb_vs {self.pairs[pair_index].client.virtual_server_ip} {self.pairs[pair_index].client.virtual_server_port}')
            self.ssh_apv.execute_command('slb virtual enable udp_slb_vs')
            self.ssh_apv.execute_command('slb policy default udp_slb_vs udp_slb_rs_group')
        
        
        
    def setupTCPLoadBalancer(self,pair_index,dry_run=False):
        if dry_run:
            print(f"Dry run: Setting up TCP Load Balancer for pair index {pair_index}")
            print(f"slb real tcp tcp_rs_{pair_index} {self.pairs[pair_index].server.server_ip} {self.pairs[pair_index].server.listen_port}")
            
            print('slb group method tcp_slb_rs_group rr')
            print(f'slb group member tcp_slb_rs_group tcp_rs_{pair_index}')
            print('slb group enable tcp_slb_rs_group')
            
            print(f'slb virtual tcp tcp_slb_vs {self.pairs[pair_index].client.virtual_server_ip} {self.pairs[pair_index].client.virtual_server_port}')
            print('slb virtual enable tcp_slb_vs')
            print('slb policy default tcp_slb_vs tcp_slb_rs_group')
            
        else:
        # setup TCP real servers  
            self.ssh_apv.execute_command(f"slb real tcp tcp_rs_{pair_index} {self.pairs[pair_index].server.server_ip} {self.pairs[pair_index].server.listen_port}")
        
            self.ssh_apv.execute_command('slb group method tcp_slb_rs_group rr')     
            self.ssh_apv.execute_command(f'slb group member tcp_slb_rs_group tcp_rs_{pair_index}')
            self.ssh_apv.execute_command('slb group enable tcp_slb_rs_group')
            
            self.ssh_apv.execute_command(f'slb virtual tcp tcp_slb_vs {self.pairs[pair_index].client.virtual_server_ip} {self.pairs[pair_index].client.virtual_server_port}')
            self.ssh_apv.execute_command('slb virtual enable tcp_slb_vs')
            self.ssh_apv.execute_command('slb policy default tcp_slb_vs tcp_slb_rs_group')
        
        
    
    def setup_apv(self, dry_run=False):
        self.ssh_apv.execute_command('enable',real_time=True)
        self.ssh_apv.execute_command(f'{self.apv_enable_password}',real_time=True)
        
        self.ssh_apv.execute_command('config terminal',real_time=True)
        for i in range(len(self.pairs)):
            protocol = self.pairs[i].protocol.lower()
            if protocol == 'udp':
                print('UDP')
                self.setupUDPLoadBalancer(pair_index=i,dry_run=dry_run)
            elif protocol == 'tcp':
                print('TCP')
                self.setupTCPLoadBalancer(pair_index=i,dry_run=dry_run)
            else:
                raise ValueError(f"Unsupported protocol: {protocol}")
    
    def connect(self):
        self.ssh_apv.connect(persistent_session=True,)
        
    def disconnect(self):
        self.ssh_apv.close()
        
if __name__ == "__main__":
    config = Config()
    config.from_yaml("config.yaml")
    apv_setup = APVSetup(config)
    apv_setup.connect()
    apv_setup.setup_apv(dry_run=True)
    apv_setup.disconnect()
