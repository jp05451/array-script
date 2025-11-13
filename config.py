from dataclasses import dataclass, field
from typing import Dict, Any
import yaml


@dataclass
class TrafficGeneratorPair:
    """流量產生器配對配置"""
    client_nic_pci: str = ""
    client_ip: str = ""
    source_ip_nums: int = 0
    client_gw: str = ""
    server_nic_pci: str = ""
    server_ip: str = ""
    server_gw: str = ""
    listen_start_port: int = 0
    slb_port_nums: int = 0
    protocol: str = "tcp"


@dataclass
class TrafficGenerator:
    """流量產生器配置"""
    management_ip: str = ""
    management_port: int = 0
    pairs: TrafficGeneratorPair = field(default_factory=TrafficGeneratorPair)


@dataclass
class TestConfig:
    """測試配置"""
    apv_management_ip: str = ""
    apv_managment_port: int = 0
    traffic_generator: TrafficGenerator = field(default_factory=TrafficGenerator)


@dataclass
class Config:
    """主配置類別"""
    test: TestConfig = field(default_factory=TestConfig)

    # 保留舊的連線資訊作為預設值
    HOST: str = '192.168.1.207'
    USER: str = 'root'
    PASSWORD: str = 'array'

    APV_HOST: str = '192.168.1.247'
    APV_USER: str = 'array'
    APV_PASSWORD: str = 'aclab@6768'

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
        pairs_data = tg_data.get('pairs', [])

        # 將 pairs 列表轉換為字典
        pairs_dict = {}
        for item in pairs_data:
            if isinstance(item, dict):
                pairs_dict.update(item)

        # 建立 TrafficGeneratorPair 物件
        pair = TrafficGeneratorPair(
            client_nic_pci=pairs_dict.get('client_nic_pci', ''),
            client_ip=pairs_dict.get('client_ip', ''),
            source_ip_nums=pairs_dict.get('source_ip_nums', 0),
            client_gw=pairs_dict.get('client_gw', ''),
            server_nic_pci=pairs_dict.get('server_nic_pci', ''),
            server_ip=pairs_dict.get('server_ip', ''),
            server_gw=pairs_dict.get('server_gw', ''),
            listen_start_port=pairs_dict.get('listen_start_port', 0),
            slb_port_nums=pairs_dict.get('slb_port_nums', 0),
            protocol=pairs_dict.get('protocol', 'tcp')
        )

        # 建立 TrafficGenerator 物件
        traffic_generator = TrafficGenerator(
            management_ip=tg_data.get('management_ip', ''),
            management_port=tg_data.get('management_port', 22),
            pairs=pair
        )

        # 建立 TestConfig 物件
        config.test = TestConfig(
            apv_management_ip=test_data.get('apv_management_ip', ''),
            apv_managment_port=test_data.get('apv_managment_port', 0),
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
                'traffic_generator': {
                    'management_ip': self.test.traffic_generator.management_ip,
                    'management_port': self.test.traffic_generator.management_port,
                    'pairs': {
                        'client_nic_pci': self.test.traffic_generator.pairs.client_nic_pci,
                        'client_ip': self.test.traffic_generator.pairs.client_ip,
                        'source_ip_nums': self.test.traffic_generator.pairs.source_ip_nums,
                        'client_gw': self.test.traffic_generator.pairs.client_gw,
                        'server_nic_pci': self.test.traffic_generator.pairs.server_nic_pci,
                        'server_ip': self.test.traffic_generator.pairs.server_ip,
                        'server_gw': self.test.traffic_generator.pairs.server_gw,
                        'listen_start_port': self.test.traffic_generator.pairs.listen_start_port,
                        'slb_port_nums': self.test.traffic_generator.pairs.slb_port_nums,
                        'protocol': self.test.traffic_generator.pairs.protocol,
                    }
                }
            }
        }