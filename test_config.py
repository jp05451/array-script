#!/usr/bin/env python3
"""Test configuration loading"""

from config import Config

if __name__ == "__main__":
    try:
        # Load configuration
        config=Config()
        config.from_yaml("config.yaml")
        print("=" * 60)
        print("Test Configuration Loading")
        print("=" * 60)
        print("✓ Configuration file loaded successfully\n")

        # Display configuration information
        print("=== APV Configuration ===")
        print(f"Management IP: {config.test.apv_management_ip}")
        print(f"Management Port: {config.test.apv_management_port}")
        print(f"Username: {config.test.apv_username}")
        print(f"Password: {config.test.apv_password}")

        print("\n=== Traffic Generator Configuration ===")
        tg = config.test.traffic_generator
        print(f"Management IP: {tg.management_ip}")
        print(f"Management Port: {tg.management_port}")
        print(f"Username: {tg.username}")
        print(f"Password: {tg.password}")
        print(f"DPDK Path: {tg.dpdk_path}")
        print(f"Dperf Path: {tg.dperf_path}")

        print(f"\n=== Pairs Configuration (Total {len(tg.pairs)} sets) ===")

        for i, pair in enumerate(tg.pairs):
            print(f"\n{'=' * 60}")
            print(f"[Pair {i}]")
            print('=' * 60)

            print("\n=== Client Configuration ===")
            client = pair.client
            print(f"NIC PCI: {client.client_nic_pci}")
            print(f"NIC Name: {client.client_nic_name}")
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
            print(f"Virtual Server IP: {client.virtual_server_ip}")
            print(f"Virtual Server Port: {client.virtual_server_port}")
            print(f"Virtual Server Port Nums: {client.virtual_server_port_nums}")

            print("\n=== Server Configuration ===")
            server = pair.server
            print(f"NIC PCI: {server.server_nic_pci}")
            print(f"NIC Name: {server.server_nic_name}")
            print(f"IP: {server.server_ip}")
            print(f"Gateway: {server.server_gw}")
            print(f"Duration: {server.server_duration}")
            print(f"CPU Core: {server.server_cpu_core}")
            print(f"TX Burst: {server.tx_burst}")
            print(f"Keepalive: {server.keepalive}")
            print(f"RSS: {server.rss}")
            print(f"Socket Mem: {server.socket_mem}")
            print(f"Listen Port: {server.listen_port}")
            print(f"Listen Port Nums: {server.listen_port_nums}")

            print("\n=== Shared Configuration ===")
            print(f"Payload Size: {pair.payload_size}")
            print(f"Protocol: {pair.protocol}")

        print("\n=== Test to_dict ===")
        config_dict = config.to_dict()
        print("✓ Successfully converted to dictionary")

        # Display number of pairs
        pairs_count = len(config_dict['test']['traffic_generator']['pairs'])
        print(f"Number of Pairs: {pairs_count}")

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
