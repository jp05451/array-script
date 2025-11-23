#!/usr/bin/env python3
"""測試配置載入"""

from config import Config

if __name__ == "__main__":
    # 載入配置
    config = Config.from_yaml("config.yaml")

    # 顯示配置資訊
    print("=== APV 配置 ===")
    print(f"Management IP: {config.test.apv_management_ip}")
    print(f"Management Port: {config.test.apv_managment_port}")
    print(f"Username: {config.test.apv_username}")
    print(f"Password: {config.test.apv_password}")

    print("\n=== Traffic Generator 配置 ===")
    tg = config.test.traffic_generator
    print(f"Management IP: {tg.management_ip}")
    print(f"Management Port: {tg.management_port}")
    print(f"Username: {tg.username}")
    print(f"Password: {tg.password}")

    print("\n=== Client 配置 ===")
    client = tg.pairs.client
    print(f"NIC PCI: {client.client_nic_pci}")
    print(f"IP: {client.client_ip}")
    print(f"Source IP Nums: {client.source_ip_nums}")
    print(f"Gateway: {client.client_gw}")
    print(f"Duration: {client.client_duration}")
    print(f"CPU Core: {client.client_cpu_core}")
    print(f"TX Burst: {client.tx_burst}")
    print(f"Launch Num: {client.launch_num}")
    print(f"CC: {client.cc}")
    print(f"Keepalive: {client.keepalive}")
    print(f"RSS: {client.rss}")
    print(f"Socket Mem: {client.socket_mem}")

    print("\n=== Server 配置 ===")
    server = tg.pairs.server
    print(f"NIC PCI: {server.server_nic_pci}")
    print(f"IP: {server.server_ip}")
    print(f"Gateway: {server.server_gw}")
    print(f"Duration: {server.server_duration}")
    print(f"CPU Core: {server.server_cpu_core}")
    print(f"TX Burst: {server.tx_burst}")
    print(f"Keepalive: {server.keepalive}")
    print(f"RSS: {server.rss}")
    print(f"Socket Mem: {server.socket_mem}")

    print("\n=== Shared 配置 ===")
    pairs = tg.pairs
    print(f"Payload Size: {pairs.payload_size}")
    print(f"Listen Start Port: {pairs.listen_start_port}")
    print(f"Listen Port Nums: {pairs.listen_port_nums}")
    print(f"Protocol: {pairs.protocol}")

    print("\n=== 測試 to_dict ===")
    config_dict = config.to_dict()
    print("成功轉換為字典")
