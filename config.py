from dataclasses import dataclass, field
from typing import Dict, Any, List
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
    client_nic_name: str = ""
    client_nic_driver: str = "i40e"
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
    virtual_server_ip: str = ""
    virtual_server_port: int = 0
    virtual_server_port_nums: int = 1


@dataclass
class ServerConfig:
    """伺服器配置"""
    server_nic_pci: str = ""
    server_nic_name: str = ""
    server_nic_driver: str = "i40e"
    server_ip: str = ""
    server_gw: str = ""
    server_duration: str = ""
    server_cpu_core: int = 0
    tx_burst: int = 0
    keepalive: str = ""
    rss: bool = False
    socket_mem: int = 0
    listen_port: int = 0
    listen_port_nums: int = 1


@dataclass
class TrafficGeneratorPair:
    """流量產生器配對配置"""
    client: ClientConfig = field(default_factory=ClientConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    payload_size: int = 0
    protocol: str = "tcp"


@dataclass
class TrafficGenerator:
    """流量產生器配置"""
    management_ip: str = ""
    management_port: int = 0
    username: str = ""
    password: str = ""
    dpdk_path: str = ""
    dperf_path: str = ""
    hugepage_frames: int = 2
    hugepage_size: str = "1G"
    pairs: List[TrafficGeneratorPair] = field(default_factory=list)


@dataclass
class TestConfig:
    """測試配置"""
    apv_management_ip: str = ""
    apv_management_port: int = 0
    apv_username: str = ""
    apv_password: str = ""
    apv_enable_password: str = ""
    traffic_generator: TrafficGenerator = field(default_factory=TrafficGenerator)


class Config:
    """主配置類別"""
    def __init__(self, yaml_path: str = None):
        """初始化配置

        Args:
            yaml_path: YAML 配置檔案路徑，如果提供則自動載入
        """
        self.test = TestConfig()

        if yaml_path:
            self.from_yaml(yaml_path)

    def from_yaml(self, yaml_path: str) -> None:
        """從 YAML 檔案載入配置，直接更新當前物件的屬性

        Args:
            yaml_path: YAML 配置檔案路徑
        """
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        test_data = data['test']

        # 解析 traffic_generator
        tg_data = test_data.get('traffic_generator', {})
        pairs_data_list = tg_data.get('pairs', [])

        # 解析所有的 pairs (現在是列表)
        pairs_list = []
        for pairs_data in pairs_data_list:
            # 解析 client 配置
            client_data = pairs_data.get('client', {})
            client_config = ClientConfig(
                client_nic_pci=client_data.get('client_nic_pci', ''),
                client_nic_name=client_data.get('client_nic_name', ''),
                client_nic_driver=client_data.get('client_nic_driver', 'i40e'),
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
                socket_mem=client_data.get('socket_mem', 0),
                virtual_server_ip=client_data.get('virtual_server_ip', ''),
                virtual_server_port=client_data.get('virtual_server_port', 6769),
                virtual_server_port_nums=client_data.get('server_port_nums', 1)
            )

            # 解析 server 配置
            server_data = pairs_data.get('server', {})
            server_config = ServerConfig(
                server_nic_pci=server_data.get('server_nic_pci', ''),
                server_nic_name=server_data.get('server_nic_name', ''),
                server_nic_driver=server_data.get('server_nic_driver', 'i40e'),
                server_ip=server_data.get('server_ip', ''),
                server_gw=server_data.get('server_gw', ''),
                server_duration=server_data.get('server_duration', ''),
                server_cpu_core=server_data.get('server_cpu_core', 0),
                tx_burst=server_data.get('tx_burst', 0),
                keepalive=server_data.get('keepalive', ''),
                rss=server_data.get('rss', False),
                socket_mem=server_data.get('socket_mem', 0),
                listen_port=server_data.get('listen_port', 6768),
                listen_port_nums=server_data.get('listen_port_nums', 1)
            )

            # 建立 TrafficGeneratorPair 物件
            pair = TrafficGeneratorPair(
                client=client_config,
                server=server_config,
                payload_size=pairs_data.get('payload_size', 1024),
                protocol=pairs_data.get('protocol', 'tcp')
            )
            pairs_list.append(pair)

        # 建立 TrafficGenerator 物件
        traffic_generator = TrafficGenerator(
            management_ip=tg_data.get('management_ip', ''),
            management_port=tg_data.get('management_port', 22),
            username=tg_data.get('username', ''),
            password=tg_data.get('password', ''),
            dpdk_path=tg_data.get('dpdk_path', ''),
            dperf_path=tg_data.get('dperf_path', ''),
            hugepage_frames=tg_data.get('hugepage_frames', 2),
            hugepage_size=tg_data.get('hugepage_size', '1G'),
            pairs=pairs_list
        )

        # 直接更新當前物件的 test 屬性
        self.test = TestConfig(
            apv_management_ip=test_data.get('apv_management_ip', ''),
            apv_management_port=test_data.get('apv_management_port', 0),
            apv_username=test_data.get('apv_username', ''),
            apv_password=test_data.get('apv_password', ''),
            apv_enable_password=test_data.get('apv_enable_password', ''),
            traffic_generator=traffic_generator
        )
        return self

    def to_dict(self) -> Dict[str, Any]:
        """將配置轉換為字典

        Returns:
            Dict[str, Any]: 配置字典
        """
        pairs_list = []
        for pair in self.test.traffic_generator.pairs:
            pairs_list.append({
                'client': {
                    'client_nic_pci': pair.client.client_nic_pci,
                    'client_nic_name': pair.client.client_nic_name,
                    'client_nic_driver': pair.client.client_nic_driver,
                    'client_ip': pair.client.client_ip,
                    'source_ip_nums': pair.client.source_ip_nums,
                    'client_gw': pair.client.client_gw,
                    'client_duration': pair.client.client_duration,
                    'client_cpu_core': pair.client.client_cpu_core,
                    'tx_burst': pair.client.tx_burst,
                    'launch_num': pair.client.launch_num,
                    'cc': pair.client.cc,
                    'keepalive': pair.client.keepalive,
                    'rss': pair.client.rss,
                    'socket_mem': pair.client.socket_mem,
                    'virtual_server_ip': pair.client.virtual_server_ip,
                    'virtual_server_port': pair.client.virtual_server_port,
                    'virtual_server_port_nums': pair.client.virtual_server_port_nums,
                },
                'server': {
                    'server_nic_pci': pair.server.server_nic_pci,
                    'server_nic_name': pair.server.server_nic_name,
                    'server_nic_driver': pair.server.server_nic_driver,
                    'server_ip': pair.server.server_ip,
                    'server_gw': pair.server.server_gw,
                    'server_duration': pair.server.server_duration,
                    'server_cpu_core': pair.server.server_cpu_core,
                    'tx_burst': pair.server.tx_burst,
                    'keepalive': pair.server.keepalive,
                    'rss': pair.server.rss,
                    'socket_mem': pair.server.socket_mem,
                    'listen_port': pair.server.listen_port,
                    'listen_port_nums': pair.server.listen_port_nums,
                },
                'payload_size': pair.payload_size,
                'protocol': pair.protocol,
            })

        return {
            'test': {
                'apv_management_ip': self.test.apv_management_ip,
                'apv_management_port': self.test.apv_management_port,
                'apv_username': self.test.apv_username,
                'apv_password': self.test.apv_password,
                'apv_enable_password': self.test.apv_enable_password,
                'traffic_generator': {
                    'management_ip': self.test.traffic_generator.management_ip,
                    'management_port': self.test.traffic_generator.management_port,
                    'username': self.test.traffic_generator.username,
                    'password': self.test.traffic_generator.password,
                    'dpdk_path': self.test.traffic_generator.dpdk_path,
                    'dperf_path': self.test.traffic_generator.dperf_path,
                    'hugepage_frames': self.test.traffic_generator.hugepage_frames,
                    'hugepage_size': self.test.traffic_generator.hugepage_size,
                    'pairs': pairs_list
                }
            }
        }