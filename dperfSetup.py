from ssh_executor import SSHExecutor
from config import Config


class dperf:
    def __init__(self, config: Config, pair_index: int = 0, log_path: str = None):
        self.config = config
        self.pair_index = pair_index
        self.pair = config.test.traffic_generator.pairs[pair_index]
        if log_path is None or log_path == "":
            log_path = f"./logs/dperf_pair{pair_index}.log"
        self.executor = SSHExecutor(
            config.test.traffic_generator.management_ip,
            config.test.traffic_generator.management_port,
            config.test.traffic_generator.username,
            config.test.traffic_generator.password,
            log_path=log_path,
        )

    def connect(self):
        """連接到遠端主機"""
        self.executor.connect(persistent_session=True)
        
    def disconnect(self):
        """斷開與遠端主機的連接"""
        self.executor.close()

    def parseOutput(self, log):
        log = log[0]
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

            print(result)
            print("統計數據 (dict 格式):")
            print(stats_dict)
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
            # 設定 hugepages
            self.setHugePages()
            # 綁定 NICs
            self.bindNICs()
            # 建立配置檔案
            self.setupConfig()

        except Exception as e:
            print(f"設定 dperf 環境失敗: {e}")
            raise

    def DperfServer(self):
        pass

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
    test.connect()
    test.setupEnv()
    test.disconnect()
