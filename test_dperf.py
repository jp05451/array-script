#!/usr/bin/env python3
"""測試 dperf 類別的各種功能"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
from dperfSetup import dperf
from config import (
    Config,
    TestConfig,
    TrafficGenerator,
    TrafficGeneratorPair,
    ClientConfig,
    ServerConfig,
)


class TestDperfInit(unittest.TestCase):
    """測試 dperf 類別初始化"""

    def setUp(self):
        """設定測試環境"""
        self.config = self._create_test_config()

    def _create_test_config(self):
        """創建測試用配置"""
        config = Config()
        config.test = TestConfig()
        config.test.traffic_generator = TrafficGenerator()
        config.test.traffic_generator.management_ip = "192.168.1.100"
        config.test.traffic_generator.management_port = 22
        config.test.traffic_generator.username = "testuser"
        config.test.traffic_generator.password = "testpass"
        config.test.traffic_generator.dpdk_path = "/opt/dpdk"
        config.test.traffic_generator.dperf_path = "/opt/dperf"
        config.test.traffic_generator.hugepage_frames = 4
        config.test.traffic_generator.hugepage_size = "1G"

        # 創建測試 pair
        pair = TrafficGeneratorPair()
        pair.protocol = "tcp"
        pair.payload_size = 1024

        pair.client = ClientConfig()
        pair.client.client_nic_pci = "0000:01:00.0"
        pair.client.client_nic_name = "eth0"
        pair.client.client_nic_driver = "i40e"
        pair.client.client_ip = "192.168.10.1"
        pair.client.source_ip_nums = 100
        pair.client.client_gw = "192.168.10.254"
        pair.client.client_duration = "30s"
        pair.client.client_cpu_core = 1
        pair.client.tx_burst = 32
        pair.client.launch_num = 1000
        pair.client.cc = "cubic"
        pair.client.keepalive = "30"
        pair.client.rss = True
        pair.client.socket_mem = 1024
        pair.client.virtual_server_ip = "192.168.20.1"
        pair.client.virtual_server_port = 80
        pair.client.virtual_server_port_nums = 1

        pair.server = ServerConfig()
        pair.server.server_nic_pci = "0000:02:00.0"
        pair.server.server_nic_name = "eth1"
        pair.server.server_nic_driver = "i40e"
        pair.server.server_ip = "192.168.20.1"
        pair.server.server_gw = "192.168.20.254"
        pair.server.server_duration = "60s"
        pair.server.server_cpu_core = 2
        pair.server.tx_burst = 32
        pair.server.keepalive = "30"
        pair.server.rss = True
        pair.server.socket_mem = 1024
        pair.server.listend_port = 80
        pair.server.listend_port_nums = 1

        config.test.traffic_generator.pairs = [pair]

        return config

    @patch("dperfSetup.SSHExecutor")
    def test_init_default_pair_index(self, mock_ssh):
        """測試預設 pair_index 初始化"""
        d = dperf(self.config)

        self.assertEqual(d.pair_index, 0)
        self.assertEqual(d.pair, self.config.test.traffic_generator.pairs[0])
        mock_ssh.assert_called_once_with(
            "192.168.1.100", 22, "testuser", "testpass", log_path="./logs/dperf_pair0.log"
        )

    @patch("dperfSetup.SSHExecutor")
    def test_init_custom_pair_index(self, mock_ssh):
        """測試自訂 pair_index 初始化"""
        # 添加第二個 pair
        pair2 = TrafficGeneratorPair()
        pair2.protocol = "udp"
        self.config.test.traffic_generator.pairs.append(pair2)

        d = dperf(self.config, pair_index=1)

        self.assertEqual(d.pair_index, 1)
        self.assertEqual(d.pair, self.config.test.traffic_generator.pairs[1])
        self.assertEqual(d.pair.protocol, "udp")

    @patch("dperfSetup.SSHExecutor")
    def test_init_custom_log_path(self, mock_ssh):
        """測試自訂 log 路徑"""
        custom_log = "/custom/path/test.log"
        d = dperf(self.config, log_path=custom_log)

        mock_ssh.assert_called_once_with(
            "192.168.1.100", 22, "testuser", "testpass", log_path=custom_log
        )


class TestDperfConnection(unittest.TestCase):
    """測試 dperf 連接管理"""

    def setUp(self):
        """設定測試環境"""
        self.config = TestDperfInit()._create_test_config()

    @patch("dperfSetup.SSHExecutor")
    def test_connect(self, mock_ssh):
        """測試連接功能"""
        d = dperf(self.config)
        d.connect()

        d.executor.connect.assert_called_once_with(persistent_session=True)

    @patch("dperfSetup.SSHExecutor")
    def test_disconnect(self, mock_ssh):
        """測試斷開連接功能"""
        d = dperf(self.config)
        d.disconnect()

        d.executor.close.assert_called_once()


class TestDperfParseOutput(unittest.TestCase):
    """測試 dperf 輸出解析"""

    def setUp(self):
        """設定測試環境"""
        self.config = TestDperfInit()._create_test_config()

    @patch("dperfSetup.SSHExecutor")
    def test_parse_output_success(self, mock_ssh):
        """測試成功解析輸出"""
        d = dperf(self.config)

        # 模擬 dperf 輸出
        test_output = [
            """
dperf Test Finished
Total Numbers:
Sent:       1,000,000
Received:   1,000,000
Errors:     0
Retrans:    100
"""
        ]

        result = d.parseOutput(test_output)

        self.assertIsNotNone(result)
        self.assertEqual(result["Sent:"], 1000000)
        self.assertEqual(result["Received:"], 1000000)
        self.assertEqual(result["Errors:"], 0)
        self.assertEqual(result["Retrans:"], 100)

    @patch("dperfSetup.SSHExecutor")
    def test_parse_output_no_finish_marker(self, mock_ssh):
        """測試無 'dperf Test Finished' 標記的輸出"""
        d = dperf(self.config)

        test_output = ["Some random output without the finish marker"]

        result = d.parseOutput(test_output)

        self.assertIsNone(result)

    @patch("dperfSetup.SSHExecutor")
    def test_parse_output_complex_stats(self, mock_ssh):
        """測試複雜的統計數據解析"""
        d = dperf(self.config)

        test_output = [
            """
dperf Test Finished
Total Numbers:
Sent:       10,000,000   Received:   9,999,900
Errors:     100          Retrans:    1,000
Timeouts:   50           Connects:   500,000
"""
        ]

        result = d.parseOutput(test_output)

        self.assertEqual(result["Sent:"], 10000000)
        self.assertEqual(result["Received:"], 9999900)
        self.assertEqual(result["Errors:"], 100)
        self.assertEqual(result["Retrans:"], 1000)
        self.assertEqual(result["Timeouts:"], 50)
        self.assertEqual(result["Connects:"], 500000)


class TestDperfNICBinding(unittest.TestCase):
    """測試 NIC 綁定功能"""

    def setUp(self):
        """設定測試環境"""
        self.config = TestDperfInit()._create_test_config()

    @patch("dperfSetup.SSHExecutor")
    def test_bind_nics_success(self, mock_ssh):
        """測試成功綁定 NIC"""
        d = dperf(self.config)
        d.bindNICs()

        # 驗證執行的命令順序
        calls = d.executor.execute_command.call_args_list
        self.assertEqual(len(calls), 5)

        # 檢查 cd 命令
        self.assertIn("/opt/dpdk/usertools", calls[0][0][0])

        # 檢查 nmcli down 命令
        self.assertIn("nmcli connection down eth0", calls[1][0][0])
        self.assertIn("nmcli connection down eth1", calls[2][0][0])

        # 檢查綁定命令
        self.assertIn("dpdk-devbind.py -b vfio-pci 0000:01:00.0", calls[3][0][0])
        self.assertIn("dpdk-devbind.py -b vfio-pci 0000:02:00.0", calls[4][0][0])

    @patch("dperfSetup.SSHExecutor")
    def test_unbind_nics_success(self, mock_ssh):
        """測試成功解綁 NIC"""
        d = dperf(self.config)
        d.unbindNICs()

        calls = d.executor.execute_command.call_args_list
        self.assertEqual(len(calls), 6)

        # 檢查解綁命令
        self.assertIn("dpdk-devbind.py -b i40e 0000:01:00.0", calls[1][0][0])
        self.assertIn("dpdk-devbind.py -b i40e 0000:02:00.0", calls[2][0][0])

        # 檢查 nmcli up 命令
        self.assertIn("nmcli connection up eth0", calls[3][0][0])
        self.assertIn("nmcli connection up eth1", calls[4][0][0])

        # 檢查顯示狀態命令
        self.assertIn("dpdk-devbind.py --status", calls[5][0][0])


class TestDperfHugePages(unittest.TestCase):
    """測試 HugePages 設定"""

    def setUp(self):
        """設定測試環境"""
        self.config = TestDperfInit()._create_test_config()

    @patch("dperfSetup.SSHExecutor")
    def test_set_hugepages_1g(self, mock_ssh):
        """測試設定 1G HugePages"""
        d = dperf(self.config)
        d.setHugePages()

        calls = d.executor.execute_command.call_args_list

        # 檢查 cd 命令
        self.assertIn("/opt/dpdk/usertools", calls[0][0][0])

        # 檢查 hugepages 設定命令 (4 * 1G = 4G)
        self.assertIn("dpdk-hugepages.py -p 1G --setup 4G", calls[1][0][0])

    @patch("dperfSetup.SSHExecutor")
    def test_set_hugepages_2m(self, mock_ssh):
        """測試設定 2M HugePages"""
        self.config.test.traffic_generator.hugepage_size = "2M"
        self.config.test.traffic_generator.hugepage_frames = 1024

        d = dperf(self.config)
        d.setHugePages()

        calls = d.executor.execute_command.call_args_list

        # 檢查 hugepages 設定命令 (1024 * 2M = 2048M)
        self.assertIn("dpdk-hugepages.py -p 2M --setup 2048M", calls[1][0][0])

    @patch("dperfSetup.SSHExecutor")
    def test_set_hugepages_exception(self, mock_ssh):
        """測試 HugePages 設定失敗"""
        d = dperf(self.config)
        d.executor.execute_command.side_effect = Exception("設定失敗")

        with self.assertRaises(Exception):
            d.setHugePages()


class TestDperfConfigGeneration(unittest.TestCase):
    """測試配置檔案生成"""

    def setUp(self):
        """設定測試環境"""
        self.config = TestDperfInit()._create_test_config()

    @patch("dperfSetup.SSHExecutor")
    def test_generate_server_config(self, mock_ssh):
        """測試生成 Server 配置"""
        d = dperf(self.config)
        server_config = d.generateServerConfig()

        # 檢查必要的配置項目
        self.assertIn("mode            server", server_config)
        self.assertIn("tx_burst        32", server_config)
        self.assertIn("cpu             2", server_config)
        self.assertIn("rss", server_config)
        self.assertIn("socket_mem      1024", server_config)
        self.assertIn("protocol        tcp", server_config)
        self.assertIn("duration        60s", server_config)
        self.assertIn("payload_size    1024", server_config)
        self.assertIn("keepalive       30", server_config)
        self.assertIn("0000:02:00.0", server_config)
        self.assertIn("192.168.20.1", server_config)
        self.assertIn("192.168.20.254", server_config)
        self.assertIn("listen          80", server_config)

    @patch("dperfSetup.SSHExecutor")
    def test_generate_client_config(self, mock_ssh):
        """測試生成 Client 配置"""
        d = dperf(self.config)
        client_config = d.generateClientConfig()

        # 檢查必要的配置項目
        self.assertIn("mode            client", client_config)
        self.assertIn("tx_burst        32", client_config)
        self.assertIn("launch_num      1000", client_config)
        self.assertIn("cpu             1", client_config)
        self.assertIn("rss", client_config)
        self.assertIn("socket_mem      1024", client_config)
        self.assertIn("protocol        tcp", client_config)
        self.assertIn("payload_size    1024", client_config)
        self.assertIn("duration        30s", client_config)
        self.assertIn("cc              cubic", client_config)
        self.assertIn("keepalive       30", client_config)
        self.assertIn("0000:01:00.0", client_config)
        self.assertIn("192.168.10.1", client_config)
        self.assertIn("192.168.10.254", client_config)
        self.assertIn("192.168.20.1", client_config)

    @patch("dperfSetup.SSHExecutor")
    def test_generate_config_without_rss(self, mock_ssh):
        """測試生成不含 RSS 的配置"""
        self.config.test.traffic_generator.pairs[0].client.rss = False
        self.config.test.traffic_generator.pairs[0].server.rss = False

        d = dperf(self.config)
        server_config = d.generateServerConfig()
        client_config = d.generateClientConfig()

        # RSS 應該不在配置中（作為單獨一行）
        self.assertNotIn("\nrss\n", server_config)
        self.assertNotIn("\nrss\n", client_config)

    @patch("dperfSetup.SSHExecutor")
    def test_setup_config(self, mock_ssh):
        """測試建立配置檔案"""
        d = dperf(self.config)
        d.setupConfig()

        calls = d.executor.execute_command.call_args_list

        # 檢查 cd 命令
        self.assertIn("/opt/dperf", calls[0][0][0])

        # 檢查 mkdir 命令
        self.assertIn("mkdir -p config", calls[1][0][0])

        # 檢查 cat 命令（創建 server 配置）
        self.assertIn("cat > config/server_pair0.conf", calls[2][0][0])

        # 檢查 cat 命令（創建 client 配置）
        self.assertIn("cat > config/client_pair0.conf", calls[3][0][0])


class TestDperfSetupEnv(unittest.TestCase):
    """測試環境設定"""

    def setUp(self):
        """設定測試環境"""
        self.config = TestDperfInit()._create_test_config()

    @patch("dperfSetup.SSHExecutor")
    def test_setup_env_success(self, mock_ssh):
        """測試成功設定環境"""
        d = dperf(self.config)

        # Mock 子方法
        d.setHugePages = Mock()
        d.bindNICs = Mock()
        d.setupConfig = Mock()

        d.setupEnv()

        # 驗證所有子方法都被調用
        d.setHugePages.assert_called_once()
        d.bindNICs.assert_called_once()
        d.setupConfig.assert_called_once()

    @patch("dperfSetup.SSHExecutor")
    def test_setup_env_hugepages_failure(self, mock_ssh):
        """測試 HugePages 設定失敗時的行為"""
        d = dperf(self.config)

        d.setHugePages = Mock(side_effect=Exception("HugePages 設定失敗"))
        d.bindNICs = Mock()
        d.setupConfig = Mock()

        with self.assertRaises(Exception) as context:
            d.setupEnv()

        # 驗證 setHugePages 被調用
        d.setHugePages.assert_called_once()

        # 驗證後續步驟未被調用
        d.bindNICs.assert_not_called()
        d.setupConfig.assert_not_called()


class TestDperfIntegration(unittest.TestCase):
    """測試整合場景"""

    def setUp(self):
        """設定測試環境"""
        self.config = TestDperfInit()._create_test_config()

    @patch("dperfSetup.SSHExecutor")
    def test_full_workflow(self, mock_ssh):
        """測試完整的工作流程"""
        d = dperf(self.config)

        # Mock 子方法以避免實際執行
        d.setHugePages = Mock()
        d.bindNICs = Mock()
        d.setupConfig = Mock()

        # 模擬完整流程
        d.connect()
        d.setupEnv()
        d.disconnect()

        # 驗證調用順序
        d.executor.connect.assert_called_once_with(persistent_session=True)
        d.setHugePages.assert_called_once()
        d.bindNICs.assert_called_once()
        d.setupConfig.assert_called_once()
        d.executor.close.assert_called_once()

    @patch("dperfSetup.SSHExecutor")
    def test_multiple_pairs(self, mock_ssh):
        """測試多個 pair 的處理"""
        # 添加第二個 pair
        pair2 = TrafficGeneratorPair()
        pair2.protocol = "udp"
        pair2.payload_size = 2048
        pair2.client = ClientConfig()
        pair2.server = ServerConfig()
        self.config.test.traffic_generator.pairs.append(pair2)

        # 測試第一個 pair
        d1 = dperf(self.config, pair_index=0)
        self.assertEqual(d1.pair.protocol, "tcp")
        self.assertEqual(d1.pair.payload_size, 1024)

        # 測試第二個 pair
        d2 = dperf(self.config, pair_index=1)
        self.assertEqual(d2.pair.protocol, "udp")
        self.assertEqual(d2.pair.payload_size, 2048)


def run_tests():
    """執行所有測試"""
    # 創建測試套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加所有測試類別
    suite.addTests(loader.loadTestsFromTestCase(TestDperfInit))
    suite.addTests(loader.loadTestsFromTestCase(TestDperfConnection))
    suite.addTests(loader.loadTestsFromTestCase(TestDperfParseOutput))
    suite.addTests(loader.loadTestsFromTestCase(TestDperfNICBinding))
    suite.addTests(loader.loadTestsFromTestCase(TestDperfHugePages))
    suite.addTests(loader.loadTestsFromTestCase(TestDperfConfigGeneration))
    suite.addTests(loader.loadTestsFromTestCase(TestDperfSetupEnv))
    suite.addTests(loader.loadTestsFromTestCase(TestDperfIntegration))

    # 執行測試
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 打印總結
    print("\n" + "=" * 70)
    print("測試結果總結")
    print("=" * 70)
    print(f"執行測試數: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失敗: {len(result.failures)}")
    print(f"錯誤: {len(result.errors)}")
    print("=" * 70)

    return result.wasSuccessful()


if __name__ == "__main__":
    import sys

    success = run_tests()
    sys.exit(0 if success else 1)
