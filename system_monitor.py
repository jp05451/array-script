from ssh_executor import SSHExecutor
from output_handler import OutputHandler
from RedisDB import RedisHandler
import csv
import os
import time
from datetime import datetime
from threading import Thread


class SystemMonitor:
    """System monitor class for monitoring CPU and RAM usage of remote hosts

    Only one monitor instance is needed per machine and can be shared across multiple pairs
    """

    def __init__(self, management_ip: str, management_port: int, username: str, password: str,
                 log_path: str = "./logs", redis_host: str = "localhost", redis_port: int = 6379,
                 redis_db: int = 0, enable_redis: bool = True):
        """Initialize system monitor

        Args:
            management_ip: Remote host IP
            management_port: SSH port
            username: SSH username
            password: SSH password
            log_path: Log output path
            redis_host: Redis host address
            redis_port: Redis port
            redis_db: Redis database index
            enable_redis: Whether to enable Redis storage
        """
        self.monitoring = False
        self.monitor_data = []
        self.monitor_thread = None

        if log_path is None or log_path == "":
            log_path = "./logs"
        if not os.path.exists(log_path):
            os.makedirs(log_path, exist_ok=True)
        self.log_path = log_path

        # Create independent SSH executor for monitoring
        self.executor = SSHExecutor(
            management_ip,
            management_port,
            username,
            password,
            log_path=f"{log_path}/system_monitor.log",
        )

        # Initialize Redis Handler
        self.enable_redis = enable_redis
        self.redis_handler = None
        if self.enable_redis:
            try:
                self.redis_handler = RedisHandler(host=redis_host, port=redis_port, db=redis_db)
                if self.redis_handler.is_connected():
                    print("[SystemMonitor] Redis enabled and connected successfully")
                else:
                    print("[SystemMonitor] Redis connection failed, will use local storage only")
                    self.redis_handler = None
            except Exception as e:
                print(f"[SystemMonitor] Redis initialization failed: {e}, will use local storage only")
                self.redis_handler = None

    def connect(self):
        """Connect to remote host"""
        self.executor.connect(persistent_session=True)

    def disconnect(self):
        """Disconnect from remote host"""
        self.executor.close()
        if self.redis_handler:
            self.redis_handler.close()

    def start(self, output_file: str|None = None):
        """Start monitoring (run in a new thread)

        Args:
            output_file: Output file path, uses default if None
        """
        if self.monitoring:
            print("[SystemMonitor] Monitoring is already in progress")
            return

        self.monitor_thread = Thread(target=self._monitor_loop, args=(output_file,), name="SystemMonitor")
        self.monitor_thread.start()

    def stop(self):
        """Stop monitoring"""
        self.monitoring = False
        print("[SystemMonitor] Stopping monitoring...")

        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
            if self.monitor_thread.is_alive():
                print("[SystemMonitor] Warning: Monitoring thread failed to exit properly")

    def _monitor_loop(self, output_file: str|None = None):
        """Monitoring loop, recording CPU and RAM usage every second

        Args:
            output_file: Output file path
        """
        self.monitoring = True
        self.monitor_data = []

        print("[SystemMonitor] Starting CPU and RAM monitoring...")

        # Establish CSV file path for monitoring data
        if output_file is None:
            output_file = f"{self.log_path}/system_monitor.csv"

        # Write CSV header
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'CPU_Usage_Percent', 'RAM_Used_MB', 'RAM_Total_MB', 'RAM_Usage_Percent'])

        while self.monitoring:
            try:
                # Get current timestamp
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Get CPU usage (using top command)
                cpu_cmd = "top -bn1 | grep 'Cpu(s)' | awk '{print $8}'"
                cpu_result = self.executor.execute_command(cpu_cmd)

                # Clean output: remove ANSI escape sequences and extra newlines
                cpu_output = OutputHandler.clean_ansi(cpu_result[0]) if cpu_result else ""

                # Extract numerical part
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

                # Get RAM usage (using free command)
                ram_cmd = "free -m | grep Mem | awk '{print $3, $2}'"
                ram_result = self.executor.execute_command(ram_cmd)

                # Clean output
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

                # Record data
                data_point = {
                    'timestamp': timestamp,
                    'cpu_usage': round(cpu_usage, 2),
                    'ram_used': ram_used,
                    'ram_total': ram_total,
                    'ram_usage': round(ram_usage, 2)
                }
                self.monitor_data.append(data_point)

                # Write to CSV file
                with open(output_file, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        timestamp,
                        round(cpu_usage, 2),
                        ram_used,
                        ram_total,
                        round(ram_usage, 2)
                    ])

                # Write to Redis (if enabled)
                if self.redis_handler and self.redis_handler.is_connected():
                    success = self.redis_handler.save_monitor_data(
                        pair_index=0,  # System-level monitoring uses 0 as identifier
                        timestamp=timestamp,
                        cpu_usage=round(cpu_usage, 2),
                        ram_used=ram_used,
                        ram_total=ram_total,
                        ram_usage=round(ram_usage, 2)
                    )
                    if not success:
                        print("[SystemMonitor] Warning: Failed to write monitoring data to Redis")

                # Collect data every second
                time.sleep(1)

            except Exception as e:
                print(f"[SystemMonitor] Monitoring error: {e}")
                time.sleep(1)

        print(f"[SystemMonitor] Monitoring stopped, data saved to {output_file}")

    def get_data(self):
        """Get monitoring data

        Returns:
            list: Monitoring data list
        """
        return self.monitor_data

    def get_redis_monitor_data(self, start_time=None, end_time=None):
        """Get monitoring data from Redis

        Args:
            start_time: Start time
            end_time: End time

        Returns:
            list: Monitoring data list
        """
        if self.redis_handler and self.redis_handler.is_connected():
            return self.redis_handler.get_monitor_data(0, start_time, end_time)
        else:
            return []

    def is_monitoring(self):
        """Check if currently monitoring

        Returns:
            bool: Whether monitoring is in progress
        """
        return self.monitoring
