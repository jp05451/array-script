#!/usr/bin/env python3
"""SSH 連接並執行 shell 腳本"""

import argparse
import paramiko
import signal
import sys
from typing import Tuple, Optional
from config import Config


class SSHConnectionManager:
    """SSH 連接管理器"""

    def __init__(self, host: str, port: int, user: str, password: str):
        """
        初始化 SSH 連接管理器

        Args:
            host: 主機地址
            port: 端口號
            user: 用戶名
            password: 密碼
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self._client: Optional[paramiko.SSHClient] = None

    def connect(self) -> None:
        """建立 SSH 連接"""
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        print(f"正在連接到 {self.user}@{self.host}:{self.port}...")

        self._client.connect(
            hostname=self.host,
            port=self.port,
            username=self.user,
            password=self.password
        )

        print("連接成功！")

    def close(self) -> None:
        """關閉 SSH 連接"""
        if self._client:
            self._client.close()
            print("SSH 連接已關閉")
            self._client = None

    def is_connected(self) -> bool:
        """檢查是否已連接"""
        return self._client is not None

    def get_client(self) -> paramiko.SSHClient:
        """獲取 SSH 客戶端"""
        if not self._client:
            raise Exception("尚未建立 SSH 連接")
        return self._client

    def __enter__(self):
        """支持 with 語句"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持 with 語句"""
        self.close()


class ScriptReader:
    """腳本讀取器"""

    @staticmethod
    def read_script(script_path: str) -> str:
        """
        讀取腳本文件內容

        Args:
            script_path: 腳本文件路徑

        Returns:
            腳本內容
        """
        with open(script_path, 'r', encoding='utf-8') as f:
            return f.read()


class OutputHandler:
    """輸出處理器"""

    @staticmethod
    def print_header(script_path: str) -> None:
        """打印執行頭部信息"""
        print(f"\n開始執行 {script_path} 中的指令...\n")
        print("-" * 50)

    @staticmethod
    def print_footer(interrupted: bool = False) -> None:
        """打印執行尾部信息"""
        print("-" * 50)
        if interrupted:
            print("\n程式已被使用者中斷")
        else:
            print("\n執行完成")

    @staticmethod
    def print_exit_status(exit_status: int) -> None:
        """打印退出狀態"""
        print(f"\n執行完成，退出狀態碼：{exit_status}")

    @staticmethod
    def print_output(output: str, prefix: str = "執行結果") -> None:
        """打印標準輸出"""
        if output:
            print(f"{prefix}：")
            print(output)

    @staticmethod
    def print_error(error: str) -> None:
        """打印錯誤輸出"""
        if error:
            print(f"\n錯誤輸出：\n{error}")


class SignalHandler:
    """信號處理器"""

    def __init__(self):
        self.interrupted = False
        self._original_handler = None

    def setup(self, stdin) -> None:
        """
        設置信號處理器

        Args:
            stdin: SSH 標準輸入流
        """
        def handler(sig, frame):
            print("\n\n收到中斷信號，正在停止遠端程式...")
            try:
                stdin.write('\x03')
                stdin.flush()
            except Exception:
                pass
            self.interrupted = True

        self._original_handler = signal.signal(signal.SIGINT, handler)
        print("提示: 按 Ctrl+C 可停止程式執行\n")

    def restore(self) -> None:
        """恢復原始信號處理器"""
        if self._original_handler:
            signal.signal(signal.SIGINT, self._original_handler)


class RealTimeStreamReader:
    """實時流讀取器"""

    def __init__(self, stdout, stderr, signal_handler: SignalHandler):
        """
        初始化實時流讀取器

        Args:
            stdout: 標準輸出流
            stderr: 標準錯誤流
            signal_handler: 信號處理器
        """
        self.stdout = stdout
        self.stderr = stderr
        self.signal_handler = signal_handler

    def read(self) -> None:
        """讀取並實時打印輸出"""
        try:
            # 即時讀取輸出
            while not self.stdout.channel.exit_status_ready():
                if self.signal_handler.interrupted:
                    self._read_remaining()
                    break
                if self.stdout.channel.recv_ready():
                    output = self.stdout.channel.recv(1024).decode('utf-8')
                    print(output, end='', flush=True)

            # 讀取剩餘輸出
            if not self.signal_handler.interrupted:
                self._read_remaining()

            # 讀取錯誤輸出
            error = self.stderr.read().decode('utf-8')
            if error:
                OutputHandler.print_error(error)

        except Exception as e:
            print(f"\n執行過程中發生錯誤：{e}")

    def _read_remaining(self) -> None:
        """讀取剩餘的輸出"""
        remaining = self.stdout.read().decode('utf-8')
        if remaining:
            print(remaining, end='', flush=True)


class CommandExecutor:
    """命令執行器"""

    def __init__(self, ssh_client: paramiko.SSHClient):
        """
        初始化命令執行器

        Args:
            ssh_client: SSH 客戶端
        """
        self.ssh_client = ssh_client

    def execute_simple(self, command: str) -> Tuple[str, str, int]:
        """
        執行簡單命令（等待完成）

        Args:
            command: 要執行的命令

        Returns:
            (output, error, exit_status) 元組
        """
        stdin, stdout, stderr = self.ssh_client.exec_command(command)

        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        exit_status = stdout.channel.recv_exit_status()

        return output, error, exit_status

    def execute_realtime(self, command: str) -> None:
        """
        執行命令並實時輸出

        Args:
            command: 要執行的命令
        """
        stdin, stdout, stderr = self.ssh_client.exec_command(command, get_pty=True)

        signal_handler = SignalHandler()
        signal_handler.setup(stdin)

        reader = RealTimeStreamReader(stdout, stderr, signal_handler)
        reader.read()

        OutputHandler.print_footer(signal_handler.interrupted)


class SSHExecutor:
    """SSH 執行器類別（高層封裝）"""

    def __init__(self, config: Config):
        """
        初始化 SSH 執行器

        Args:
            config: Config 物件，包含連接資訊
        """
        self.connection_manager = SSHConnectionManager(
            host=config.HOST,
            port=config.PORT,
            user=config.USER,
            password=config.PASSWORD
        )
        self._executor: Optional[CommandExecutor] = None

    def connect(self) -> None:
        """建立 SSH 連接"""
        self.connection_manager.connect()
        self._executor = CommandExecutor(self.connection_manager.get_client())

    def execute_script(self, script_path: str, real_time: bool = False) -> Optional[Tuple[str, str, int]]:
        """
        執行指定的 shell 腳本

        Args:
            script_path: shell 腳本的路徑
            real_time: 是否即時輸出 (預設: False)

        Returns:
            如果 real_time=False，返回 (output, error, exit_status)，否則返回 None
        """
        if not self._executor:
            raise Exception("尚未建立 SSH 連接")

        commands = ScriptReader.read_script(script_path)
        OutputHandler.print_header(script_path)

        if real_time:
            self._executor.execute_realtime(commands)
            return None
        else:
            output, error, exit_status = self._executor.execute_simple(commands)

            OutputHandler.print_output(output)
            OutputHandler.print_error(error)
            OutputHandler.print_footer()
            OutputHandler.print_exit_status(exit_status)

            return output, error, exit_status

    def execute_command(self, command: str) -> Optional[Tuple[str, str, int]]:
        """
        執行單一指令

        Args:
            command: 要執行的指令

        Returns:
            (output, error, exit_status) 元組，發生錯誤時返回 None
        """
        try:
            if not self._executor:
                raise Exception("尚未建立 SSH 連接")

            return self._executor.execute_simple(command)
        except Exception as e:
            print(f"執行指令時發生錯誤：{e}")
            return None

    def close(self) -> None:
        """關閉 SSH 連接"""
        self.connection_manager.close()
        self._executor = None

    def __enter__(self):
        """支持 with 語句"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持 with 語句"""
        self.close()


def main():
    """主程式"""
    parser = argparse.ArgumentParser(description='透過 SSH 執行遠端 shell 腳本')
    parser.add_argument('script', help='要執行的 shell 腳本路徑')
    parser.add_argument('--real-time', action='store_true',
                       help='即時顯示執行輸出（預設：等待執行完成後顯示）')
    args = parser.parse_args()

    # 載入配置
    config = Config()

    # 使用 with 語句自動管理連接
    try:
        with SSHExecutor(config) as executor:
            executor.execute_script(args.script, real_time=args.real_time)
    except KeyboardInterrupt:
        print("\n程式已被使用者中斷")
        sys.exit(130)
    except Exception as e:
        print(f"發生錯誤：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
