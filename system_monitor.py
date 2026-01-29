from ssh_executor import SSHExecutor
from output_handler import OutputHandler
from RedisDB import RedisHandler
import csv
import os
import time
from datetime import datetime
from threading import Thread


class SystemMonitor:
    """系統監控類別，用於監控遠端主機的 CPU 和 RAM 使用率

    一台機器只需要一個 monitor 實例，可以被多個 pair 共享使用
    """

    def __init__(self, management_ip: str, management_port: int, username: str, password: str,
                 log_path: str = "./logs", redis_host: str = "localhost", redis_port: int = 6379,
                 redis_db: int = 0, enable_redis: bool = True):
        """初始化系統監控器

        Args:
            management_ip: 遠端主機 IP
            management_port: SSH 埠號
            username: SSH 使用者名稱
            password: SSH 密碼
            log_path: 日誌輸出路徑
            redis_host: Redis 主機位址
            redis_port: Redis 埠號
            redis_db: Redis 資料庫編號
            enable_redis: 是否啟用 Redis 儲存
        """
        self.monitoring = False
        self.monitor_data = []
        self.monitor_thread = None

        if log_path is None or log_path == "":
            log_path = "./logs"
        if not os.path.exists(log_path):
            os.makedirs(log_path, exist_ok=True)
        self.log_path = log_path

        # 建立獨立的 SSH executor 用於監控
        self.executor = SSHExecutor(
            management_ip,
            management_port,
            username,
            password,
            log_path=f"{log_path}/system_monitor.log",
        )

        # 初始化 Redis Handler
        self.enable_redis = enable_redis
        self.redis_handler = None
        if self.enable_redis:
            try:
                self.redis_handler = RedisHandler(host=redis_host, port=redis_port, db=redis_db)
                if self.redis_handler.is_connected():
                    print("[SystemMonitor] Redis 已啟用並成功連接")
                else:
                    print("[SystemMonitor] Redis 連接失敗，將僅使用本地儲存")
                    self.redis_handler = None
            except Exception as e:
                print(f"[SystemMonitor] Redis 初始化失敗: {e}，將僅使用本地儲存")
                self.redis_handler = None

    def connect(self):
        """連接到遠端主機"""
        self.executor.connect(persistent_session=True)

    def disconnect(self):
        """斷開與遠端主機的連接"""
        self.executor.close()
        if self.redis_handler:
            self.redis_handler.close()

    def start(self, output_file: str = None):
        """開始監控（在新執行緒中執行）

        Args:
            output_file: 輸出檔案路徑，若為 None 則使用預設路徑
        """
        if self.monitoring:
            print("[SystemMonitor] 監控已在執行中")
            return

        self.monitor_thread = Thread(target=self._monitor_loop, args=(output_file,), name="SystemMonitor")
        self.monitor_thread.start()

    def stop(self):
        """停止監控"""
        self.monitoring = False
        print("[SystemMonitor] 正在停止監控...")

        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
            if self.monitor_thread.is_alive():
                print("[SystemMonitor] 警告: 監控線程未能正常結束")

    def _monitor_loop(self, output_file: str = None):
        """監控迴圈，每秒記錄一次 CPU 和 RAM 使用率

        Args:
            output_file: 輸出檔案路徑
        """
        self.monitoring = True
        self.monitor_data = []

        print("[SystemMonitor] 開始監控 CPU 和 RAM...")

        # 建立監控數據的 CSV 文件路徑
        if output_file is None:
            output_file = f"{self.log_path}/system_monitor.csv"

        # 寫入 CSV 標題
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'CPU_Usage_Percent', 'RAM_Used_MB', 'RAM_Total_MB', 'RAM_Usage_Percent'])

        while self.monitoring:
            try:
                # 獲取當前時間戳
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # 獲取 CPU 使用率（使用 top 命令）
                cpu_cmd = "top -bn1 | grep 'Cpu(s)' | awk '{print $8}'"
                cpu_result = self.executor.execute_command(cpu_cmd)

                # 清理輸出：移除 ANSI 轉義序列和額外的換行符
                cpu_output = OutputHandler.clean_ansi(cpu_result[0]) if cpu_result else ""

                # 提取數字部分
                cpu_lines = [line.strip() for line in cpu_output.split('\n') if line.strip()]
                cpu_idle = 0
                for line in reversed(cpu_lines):
                    try:
                        if line and not line.startswith('[') and '#' not in line:
                            cpu_idle = float(line)
                            break
                    except ValueError:
                        continue

                cpu_usage = 100 - cpu_idle

                # 獲取 RAM 使用情況（使用 free 命令）
                ram_cmd = "free -m | grep Mem | awk '{print $3, $2}'"
                ram_result = self.executor.execute_command(ram_cmd)

                # 清理輸出
                ram_output = OutputHandler.clean_ansi(ram_result[0]) if ram_result else ""
                ram_lines = [line.strip() for line in ram_output.split('\n') if line.strip()]

                ram_used = 0
                ram_total = 0
                ram_usage = 0

                for line in reversed(ram_lines):
                    try:
                        if line and not line.startswith('[') and '#' not in line:
                            ram_parts = line.split()
                            if len(ram_parts) >= 2:
                                ram_used = int(ram_parts[0])
                                ram_total = int(ram_parts[1])
                                ram_usage = (ram_used / ram_total) * 100
                                break
                    except (ValueError, IndexError):
                        continue

                # 記錄數據
                data_point = {
                    'timestamp': timestamp,
                    'cpu_usage': round(cpu_usage, 2),
                    'ram_used': ram_used,
                    'ram_total': ram_total,
                    'ram_usage': round(ram_usage, 2)
                }
                self.monitor_data.append(data_point)

                # 寫入 CSV 文件
                with open(output_file, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        timestamp,
                        round(cpu_usage, 2),
                        ram_used,
                        ram_total,
                        round(ram_usage, 2)
                    ])

                # 寫入 Redis（如果啟用）
                if self.redis_handler and self.redis_handler.is_connected():
                    success = self.redis_handler.save_monitor_data(
                        pair_index=0,  # 系統級監控使用 0 作為標識
                        timestamp=timestamp,
                        cpu_usage=round(cpu_usage, 2),
                        ram_used=ram_used,
                        ram_total=ram_total,
                        ram_usage=round(ram_usage, 2)
                    )
                    if not success:
                        print("[SystemMonitor] 警告: 監控數據寫入 Redis 失敗")

                # 每秒收集一次數據
                time.sleep(1)

            except Exception as e:
                print(f"[SystemMonitor] 監控錯誤: {e}")
                time.sleep(1)

        print(f"[SystemMonitor] 監控已停止，數據已保存到 {output_file}")

    def get_data(self):
        """獲取監控數據

        Returns:
            list: 監控數據列表
        """
        return self.monitor_data

    def get_redis_monitor_data(self, start_time=None, end_time=None):
        """從 Redis 獲取監控數據

        Args:
            start_time: 開始時間
            end_time: 結束時間

        Returns:
            list: 監控數據列表
        """
        if self.redis_handler and self.redis_handler.is_connected():
            return self.redis_handler.get_monitor_data(0, start_time, end_time)
        else:
            return []

    def is_monitoring(self):
        """檢查是否正在監控

        Returns:
            bool: 是否正在監控
        """
        return self.monitoring
