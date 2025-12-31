from ssh_executor import SSHExecutor
from config import Config
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
import re
import os
import csv


class dperf:
    def __init__(self, config: Config, pair_index: int = 0, log_path: str = None,output_path: str = None):
        self.config = config
        self.pair_index = pair_index
        self.pair = config.test.traffic_generator.pairs[pair_index]
        if log_path is None or log_path == "":
            log_path = "./logs"
        if not os.path.exists(log_path):
            os.makedirs(log_path, exist_ok=True)
        self.outputPath=output_path
        self.executor = SSHExecutor(
            config.test.traffic_generator.management_ip,
            config.test.traffic_generator.management_port,
            config.test.traffic_generator.username,
            config.test.traffic_generator.password,
            log_path=f"{log_path}/dperf_pair{pair_index}.log",
        )
        # 為 server 和 client 建立獨立的 executor
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

    def connect(self):
        """連接到遠端主機"""
        self.executor.connect(persistent_session=True)
        
    def disconnect(self):
        """斷開與遠端主機的連接"""
        self.executor.close()
        
    def runPairTest(self):
        """執行 dperf 測試，同時運行 server 和 client 並收集流量數據"""
        self.setupEnv()

        # 建立兩個獨立的 thread 來同時測試 server 和 client
        serverThread = Thread(target=self.serverStart, name=f"Server-Pair{self.pair_index}")
        clientThread = Thread(target=self.clientStart, name=f"Client-Pair{self.pair_index}")

        print(f"[Pair {self.pair_index}] 開始同時執行 server 和 client 測試...")
        serverThread.start()
        clientThread.start()

        # 等待兩個 thread 完成
        serverThread.join()
        clientThread.join()

        print(f"[Pair {self.pair_index}] 測試完成")
        print(f"[Pair {self.pair_index}] Server 輸出: {self.serverOutput}")
        print(f"[Pair {self.pair_index}] Client 輸出: {self.clientOutput}")
        
        self.outputResults()

        return {
            'server': self.serverOutput,
            'client': self.clientOutput
        }
        
    def outputResults(self):
        """輸出測試結果到指定路徑的檔案"""
        if self.outputPath is None or self.outputPath == "":
            self.outputPath = f"./results/dperf_pair{self.pair_index}_results.csv"
        
        # 檢查輸出目錄是否存在，如果不存在則建立
        output_dir = os.path.dirname(self.outputPath)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        with open(self.outputPath, 'w') as f:
            
            # 寫入 CSV
            writer = csv.writer(f)
            
            # 寫入標題行
            writer.writerow(['Metric', 'Server', 'Client'])
            writer.writerow(['duration'])
            
            # 取得所有可能的 key
            all_keys = set()
            if self.serverOutput:
                all_keys.update(self.serverOutput.keys())
            if self.clientOutput:
                all_keys.update(self.clientOutput.keys())
            
            # 寫入每個指標的資料
            for key in sorted(all_keys):
                server_value = self.serverOutput.get(key, 'N/A') if self.serverOutput else 'N/A'
                client_value = self.clientOutput.get(key, 'N/A') if self.clientOutput else 'N/A'
                writer.writerow([key, server_value, client_value])
        
        print(f"[Pair {self.pair_index}] 測試結果已輸出到 {self.outputPath}")


    def serverStart(self):
        """啟動 dperf server 並收集流量數據"""
        try:
            print(f"[Pair {self.pair_index}] Server: 建立連接...")
            self.server_executor.connect(persistent_session=True)

            print(f"[Pair {self.pair_index}] Server: 切換目錄到 dperf...")
            self.server_executor.execute_command(
                f"cd {self.config.test.traffic_generator.dperf_path}"
            )

            server_cmd = f"sudo ./build/dperf -c config/server_pair{self.pair_index}.conf"
            print(f"[Pair {self.pair_index}] Server: 執行命令 -> {server_cmd}")
            # log = self.server_executor.execute_command(server_cmd)
            log = self.server_executor.execute_script('shell/server.sh')

            print(f"[Pair {self.pair_index}] Server: 解析輸出...")
            output = self.parseOutput(log)
            self.serverOutput = output

            print(f"[Pair {self.pair_index}] Server: 測試完成，斷開連接")
            self.server_executor.close()
        except Exception as e:
            print(f"[Pair {self.pair_index}] Server 執行失敗: {e}")
            self.serverOutput = None

    def clientStart(self):
        """啟動 dperf client 並收集流量數據"""
        try:
            print(f"[Pair {self.pair_index}] Client: 建立連接...")
            self.client_executor.connect(persistent_session=True)

            print(f"[Pair {self.pair_index}] Client: 切換目錄到 dperf...")
            self.client_executor.execute_command(
                f"cd {self.config.test.traffic_generator.dperf_path}"
            )

            client_cmd = f"sudo ./build/dperf -c config/client_pair{self.pair_index}.conf"
            print(f"[Pair {self.pair_index}] Client: 執行命令 -> {client_cmd}")
            # log = self.client_executor.execute_command(client_cmd)
            log = self.client_executor.execute_script('shell/client.sh')


            print(f"[Pair {self.pair_index}] Client: 解析輸出...")
            output = self.parseOutput(log)
            self.clientOutput = output

            print(f"[Pair {self.pair_index}] Client: 測試完成，斷開連接")
            self.client_executor.close()
        except Exception as e:
            print(f"[Pair {self.pair_index}] Client 執行失敗: {e}")
            self.clientOutput = None

    def parseOutput(self, log):
        log = log[0]

        # 移除 ANSI 轉義序列（顏色代碼）
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
        log = ansi_escape.sub('', log)

        # 找出 "dperf Test Finished" 字串並取出之後的內容
        if "dperf Test Finished" in log:
            index = log.find("Total Numbers")
            result = log[index:].strip()

            # 將統計數據解析為 dict
            stats_dict = {}
            lines = result.split("\n")

            for line in lines[1:]:  # 跳過第一行 "Total Numbers:"
                line = line.strip()
                if not line:
                    continue

                # 分割每一行的統計項目
                parts = line.split()
                i = 0
                while i < len(parts):
                    # 每個項目是 key-value 對
                    if i + 1 < len(parts):
                        key = parts[i]
                        value = parts[i + 1]

                        # 移除數字中的逗號並轉換為整數
                        try:
                            value_clean = value.replace(",", "")
                            stats_dict[key] = int(value_clean)
                        except ValueError:
                            # 如果無法轉換為整數，保留原始字串
                            stats_dict[key] = value

                        i += 2
                    else:
                        i += 1

            # print(result)
            # print("統計數據 (dict 格式):")
            # print(stats_dict)
            return stats_dict
        else:
            print("未找到 'dperf Test Finished' 字串")
            return None

    def bindNICs(self):
        """綁定 NIC 到 DPDK 驅動程式"""
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
            raise (f"綁定 NIC 失敗: {e}")

    def unbindNICs(self):
        """解綁 NIC 從 DPDK 驅動程式，恢復原生驅動"""
        try:
            self.executor.execute_command(
                f"cd {self.config.test.traffic_generator.dpdk_path}/usertools"
            )
            # 將 NIC 綁定回原生驅動程式
            self.executor.execute_command(
                f"sudo python3 dpdk-devbind.py -b {self.pair.client.client_nic_driver} {self.pair.client.client_nic_pci}"
            )
            self.executor.execute_command(
                f"sudo python3 dpdk-devbind.py -b {self.pair.server.server_nic_driver} {self.pair.server.server_nic_pci}"
            )
            # 重新啟動網路連接
            self.executor.execute_command(
                f"nmcli connection up {self.pair.client.client_nic_name}"
            )
            self.executor.execute_command(
                f"nmcli connection up {self.pair.server.server_nic_name}"
            )
            # 顯示狀態
            self.executor.execute_command("sudo python3 dpdk-devbind.py --status")

        except Exception as e:
            raise (f"解綁 NIC 失敗: {e}")
        
    def setHugePages(self):
        """設定 hugepages

        Args:
            pages: hugepages 數量
            size: hugepage 大小 (1G 或 2M)
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
            print(f"設定 hugepages 失敗: {e}")
            raise

    def setupConfig(self):
        """建立 dperf 配置檔案"""
        print("=============建立 dperf 配置檔案=============")
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

    def setupEnv(self):
        """設定 dperf 環境"""
        try:
            self.connect()

            # 設定 hugepages
            self.setHugePages()
            # 綁定 NICs
            self.bindNICs()
            # 建立配置檔案
            self.setupConfig()

            self.disconnect()
            
        except Exception as e:
            print(f"設定 dperf 環境失敗: {e}")
            raise


    def generateServerConfig(self):
        """產生 dperf server 配置檔案"""
        server_cfg = self.pair.server

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
                f"duration        {server_cfg.server_duration}",
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
                f"listen          {server_cfg.listend_port}    {server_cfg.listend_port_nums}",
                "",
            ]
        )

        return "\n".join(config_lines)

    def generateClientConfig(self):
        """產生 dperf client 配置檔案"""
        client_cfg = self.pair.client

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
                f"duration        {client_cfg.client_duration}",
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
    
if __name__ == "__main__":
    c = Config()
    config=c.from_yaml("config.yaml")
    test=dperf(config=config, pair_index=0)
    test.setupEnv()

    output = test.runPairTest()
    # import argparse
    # parser = argparse.ArgumentParser(description="DPerf Test")
    # parser.add_argument('--server', action='store_true', help='只運行 server 測試')
    # parser.add_argument('--client', action='store_true', help='只運行 client 測試')
    # args = parser.parse_args()
    # if args.server:
    #     test.serverStart()
    # elif args.client:
    #     test.clientStart()
    # print(test.clientOutput)
    print(output)