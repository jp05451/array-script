from dataclasses import dataclass, field
from typing import Dict, Any
import yaml

@dataclass
class Client:
    """客戶端配置"""
    nic_pci: str = ""
    ip: str = ""
    gw: str = ""


@dataclass
class ClientConfig:
    """客戶端配置"""
    client_nic_pci: str = ""
    client_ip: str = ""
    source_ip_nums: int = 0
    client_gw: str = ""
    client_duration: str = ""
    client_cpu_core: int = 0
    tx_burst: int = 0
    launch_num: int = 0
    cc: str = ""
    keepalive: str = ""
    rss: bool = False
    socket_mem: int = 0


@dataclass
class ServerConfig:
    """伺服器配置"""
    server_nic_pci: str = ""
    server_ip: str = ""
    server_gw: str = ""
    server_duration: str = ""
    server_cpu_core: int = 0
    tx_burst: int = 0
    keepalive: str = ""
    rss: bool = False
    socket_mem: int = 0


@dataclass
class TrafficGeneratorPair:
    """流量產生器配對配置"""
    client: ClientConfig = field(default_factory=ClientConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    payload_size: int = 0
    listen_start_port: int = 0
    listen_port_nums: int = 0
    protocol: str = "tcp"


@dataclass
class TrafficGenerator:
    """流量產生器配置"""
    management_ip: str = ""
    management_port: int = 0
    username: str = ""
    password: str = ""
    pairs: TrafficGeneratorPair = field(default_factory=TrafficGeneratorPair)


@dataclass
class TestConfig:
    """測試配置"""
    apv_management_ip: str = ""
    apv_managment_port: int = 0
    apv_username: str = ""
    apv_password: str = ""
    traffic_generator: TrafficGenerator = field(default_factory=TrafficGenerator)


@dataclass
class Config:
    """主配置類別"""
    test: TestConfig = field(default_factory=TestConfig)

    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'Config':
        """從 YAML 檔案載入配置

        Args:
            yaml_path: YAML 配置檔案路徑

        Returns:
            Config: 配置物件
        """
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        config = cls()

        test_data = data['test']

        # 解析 traffic_generator
        tg_data = test_data.get('traffic_generator', {})
        pairs_data = tg_data.get('pairs', {})

        # 解析 client 配置
        client_data = pairs_data.get('client', {})
        client_config = ClientConfig(
            client_nic_pci=client_data.get('client_nic_pci', ''),
            client_ip=client_data.get('client_ip', ''),
            source_ip_nums=client_data.get('source_ip_nums', 0),
            client_gw=client_data.get('client_gw', ''),
            client_duration=client_data.get('client_duration', ''),
            client_cpu_core=client_data.get('client_cpu_core', 0),
            tx_burst=client_data.get('tx_burst', 0),
            launch_num=client_data.get('launch_num', 0),
            cc=client_data.get('cc', ''),
            keepalive=client_data.get('keepalive', ''),
            rss=client_data.get('rss', False),
            socket_mem=client_data.get('socket_mem', 0)
        )

        # 解析 server 配置
        server_data = pairs_data.get('server', {})
        server_config = ServerConfig(
            server_nic_pci=server_data.get('server_nic_pci', ''),
            server_ip=server_data.get('server_ip', ''),
            server_gw=server_data.get('server_gw', ''),
            server_duration=server_data.get('server_duration', ''),
            server_cpu_core=server_data.get('server_cpu_core', 0),
            tx_burst=server_data.get('tx_burst', 0),
            keepalive=server_data.get('keepalive', ''),
            rss=server_data.get('rss', False),
            socket_mem=server_data.get('socket_mem', 0)
        )

        # 建立 TrafficGeneratorPair 物件
        pair = TrafficGeneratorPair(
            client=client_config,
            server=server_config,
            payload_size=pairs_data.get('payload_size', 0),
            listen_start_port=pairs_data.get('listen_start_port', 0),
            listen_port_nums=pairs_data.get('listen_port_nums', 0),
            protocol=pairs_data.get('protocol', 'tcp')
        )

        # 建立 TrafficGenerator 物件
        traffic_generator = TrafficGenerator(
            management_ip=tg_data.get('management_ip', ''),
            management_port=tg_data.get('management_port', 22),
            username=tg_data.get('username', ''),
            password=tg_data.get('password', ''),
            pairs=pair
        )

        # 建立 TestConfig 物件
        config.test = TestConfig(
            apv_management_ip=test_data.get('apv_management_ip', ''),
            apv_managment_port=test_data.get('apv_managment_port', 0),
            apv_username=test_data.get('apv_username', ''),
            apv_password=test_data.get('apv_password', ''),
            traffic_generator=traffic_generator
        )

        return config

    def to_dict(self) -> Dict[str, Any]:
        """將配置轉換為字典

        Returns:
            Dict[str, Any]: 配置字典
        """
        return {
            'test': {
                'apv_management_ip': self.test.apv_management_ip,
                'apv_managment_port': self.test.apv_managment_port,
                'apv_username': self.test.apv_username,
                'apv_password': self.test.apv_password,
                'traffic_generator': {
                    'management_ip': self.test.traffic_generator.management_ip,
                    'management_port': self.test.traffic_generator.management_port,
                    'username': self.test.traffic_generator.username,
                    'password': self.test.traffic_generator.password,
                    'pairs': {
                        'client': {
                            'client_nic_pci': self.test.traffic_generator.pairs.client.client_nic_pci,
                            'client_ip': self.test.traffic_generator.pairs.client.client_ip,
                            'source_ip_nums': self.test.traffic_generator.pairs.client.source_ip_nums,
                            'client_gw': self.test.traffic_generator.pairs.client.client_gw,
                            'client_duration': self.test.traffic_generator.pairs.client.client_duration,
                            'client_cpu_core': self.test.traffic_generator.pairs.client.client_cpu_core,
                            'tx_burst': self.test.traffic_generator.pairs.client.tx_burst,
                            'launch_num': self.test.traffic_generator.pairs.client.launch_num,
                            'cc': self.test.traffic_generator.pairs.client.cc,
                            'keepalive': self.test.traffic_generator.pairs.client.keepalive,
                            'rss': self.test.traffic_generator.pairs.client.rss,
                            'socket_mem': self.test.traffic_generator.pairs.client.socket_mem,
                        },
                        'server': {
                            'server_nic_pci': self.test.traffic_generator.pairs.server.server_nic_pci,
                            'server_ip': self.test.traffic_generator.pairs.server.server_ip,
                            'server_gw': self.test.traffic_generator.pairs.server.server_gw,
                            'server_duration': self.test.traffic_generator.pairs.server.server_duration,
                            'server_cpu_core': self.test.traffic_generator.pairs.server.server_cpu_core,
                            'tx_burst': self.test.traffic_generator.pairs.server.tx_burst,
                            'keepalive': self.test.traffic_generator.pairs.server.keepalive,
                            'rss': self.test.traffic_generator.pairs.server.rss,
                            'socket_mem': self.test.traffic_generator.pairs.server.socket_mem,
                        },
                        'payload_size': self.test.traffic_generator.pairs.payload_size,
                        'listen_start_port': self.test.traffic_generator.pairs.listen_start_port,
                        'listen_port_nums': self.test.traffic_generator.pairs.listen_port_nums,
                        'protocol': self.test.traffic_generator.pairs.protocol,
                    }
                }
            }
        }