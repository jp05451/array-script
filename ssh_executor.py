#!/usr/bin/env python3
"""SSH 連接並執行 shell 腳本"""

import argparse
import paramiko
# import signal  # 暫時關閉 signal，因為與多線程衝突
import sys
from typing import Tuple, Optional
from config import Config
from output_handler import OutputHandler


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
            password=self.password,
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
        return False


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
        with open(script_path, "r", encoding="utf-8") as f:
            return f.read()


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
        # 暫時關閉 signal 處理，因為與多線程衝突
        # def handler(sig, frame):
        #     print("\n\n收到中斷信號，正在停止遠端程式...")
        #     try:
        #         stdin.write("\x03")
        #         stdin.flush()
        #     except Exception:
        #         pass
        #     self.interrupted = True

        # self._original_handler = signal.signal(signal.SIGINT, handler)
        # print("提示: 按 Ctrl+C 可停止程式執行\n")
        pass

    def stop(self) -> None:
        """標記為已中斷"""
        self.interrupted = True

    def restore(self) -> None:
        """恢復原始信號處理器"""
        # 暫時關閉 signal 處理，因為與多線程衝突
        # if self._original_handler:
        #     signal.signal(signal.SIGINT, self._original_handler)
        pass


class RealTimeStreamReader:
    """實時流讀取器"""

    def __init__(
        self,
        stdout,
        stderr,
        signal_handler: SignalHandler,
        output_handler: OutputHandler,
    ):
        """
        初始化實時流讀取器

        Args:
            stdout: 標準輸出流
            stderr: 標準錯誤流
            signal_handler: 信號處理器
            output_handler: 輸出處理器
        """
        self.stdout = stdout
        self.stderr = stderr
        self.signal_handler = signal_handler
        self.output_handler = output_handler

    def read(self) -> None:
        """讀取並實時打印輸出"""
        try:
            # 即時讀取輸出
            while not self.stdout.channel.exit_status_ready():
                if self.signal_handler.interrupted:
                    self._read_remaining()
                    break
                if self.stdout.channel.recv_ready():
                    output = self.stdout.channel.recv(1024).decode("utf-8")
                    self.output_handler.write(output, end="", flush=True)

            # 讀取剩餘輸出
            if not self.signal_handler.interrupted:
                self._read_remaining()

            # 讀取錯誤輸出
            error = self.stderr.read().decode("utf-8")
            if error:
                self.output_handler.print_error(error)

        except Exception as e:
            self.output_handler.write(f"\n執行過程中發生錯誤：{e}")

    def _read_remaining(self) -> None:
        """讀取剩餘的輸出"""
        remaining = self.stdout.read().decode("utf-8")
        if remaining:
            self.output_handler.write(remaining, end="", flush=True)


class CommandExecutor:
    """命令執行器"""

    def __init__(self, ssh_client: paramiko.SSHClient, output_handler: OutputHandler):
        """
        初始化命令執行器

        Args:
            ssh_client: SSH 客戶端
            output_handler: 輸出處理器
        """
        self.ssh_client = ssh_client
        self.output_handler = output_handler
        self._shell = None
        self._session_active = False

    def execute_simple(self, command: str) -> Tuple[str, str, int]:
        """
        執行簡單命令（等待完成）

        Args:
            command: 要執行的命令

        Returns:
            (output, error, exit_status) 元組
        """
        stdin, stdout, stderr = self.ssh_client.exec_command(command)

        output = stdout.read().decode("utf-8")
        error = stderr.read().decode("utf-8")
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

        reader = RealTimeStreamReader(
            stdout, stderr, signal_handler, self.output_handler
        )
        reader.read()

        self.output_handler.print_footer(signal_handler.interrupted)

    def start_session(self) -> None:
        """
        啟動持久的互動式 shell session
        """
        if self._session_active:
            return

        self._shell = self.ssh_client.invoke_shell()
        self._session_active = True

        # 等待初始提示符並清除歡迎訊息
        import time
        time.sleep(0.5)
        if self._shell.recv_ready():
            self._shell.recv(4096)

    def stop_session(self) -> None:
        """
        停止持久的互動式 shell session
        """
        if self._shell:
            self._shell.close()
            self._shell = None
            self._session_active = False

    def execute_in_session(self, command: str, timeout: float = 10.0) -> str:
        """
        在持久 session 中執行命令

        Args:
            command: 要執行的命令
            timeout: 等待輸出的超時時間（秒）

        Returns:
            命令的輸出
        """
        if not self._session_active:
            raise Exception("Session 尚未啟動，請先呼叫 start_session()")

        import time

        # 發送命令
        self._shell.send(command + "\n")

        # 等待並收集輸出
        output = ""
        start_time = time.time()

        while True:
            if self._shell.recv_ready():
                chunk = self._shell.recv(4096).decode('utf-8')
                output += chunk

                # 如果看到提示符，表示命令執行完成
                # 這裡使用簡單的換行檢測，可以根據需要調整
                if chunk.endswith('$ ') or chunk.endswith('# ') or chunk.endswith('> '):
                    break

            # 檢查超時
            if time.time() - start_time > timeout:
                break

            time.sleep(0.1)

        return output

    def is_session_active(self) -> bool:
        """
        檢查 session 是否活躍

        Returns:
            True 如果 session 活躍，否則 False
        """
        return self._session_active


class SSHExecutor:
    """SSH 執行器類別（高層封裝）"""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        log_path: Optional[str] = None,
    ):
        """
        初始化 SSH 執行器

        Args:
            host: 主機地址
            port: 端口號
            user: 用戶名
            password: 密碼
            output_path: 輸出檔案路徑，若為 None 則輸出到 stdout
        """
        self.connection_manager = SSHConnectionManager(
            host=host,
            port=port,
            user=user,
            password=password,
        )
        self.output_handler = OutputHandler(log_path)
        self._executor: Optional[CommandExecutor] = None

    def connect(self, persistent_session: bool = False) -> None:
        """
        建立 SSH 連接

        Args:
            persistent_session: 是否啟用持久 session，允許在多個命令之間保持狀態（如：目錄、環境變數等）
        """
        self.connection_manager.connect()
        self._executor = CommandExecutor(
            self.connection_manager.get_client(), self.output_handler
        )
        self.persistent_session = persistent_session
        if persistent_session:
            self._executor.start_session()
    def connect_session(self) -> None:
        """建立持久 SSH 連接"""
        self.connect(persistent_session=True)
        
    def execute_script(
        self, script_path: str, real_time: bool = False
    ) -> Optional[Tuple[str, str, int]]:
        """
        執行指定的 shell 腳本

        Args:
            script_path: shell 腳本的路徑
            real_time: 是否即時輸出 (預設: False)

        Returns:
            如果 real_time=False,返回 (output, error, exit_status)，否則返回 None
        """
        if not self._executor:
            raise Exception("尚未建立 SSH 連接")

        commands = ScriptReader.read_script(script_path)
        self.output_handler.print_header(script_path)

        if real_time:
            self._executor.execute_realtime(commands)
            return None
        else:
            output, error, exit_status = self._executor.execute_simple(commands)

            self.output_handler.print_output(output)
            self.output_handler.print_error(error)
            self.output_handler.print_footer()
            self.output_handler.print_exit_status(exit_status)

            return output, error, exit_status

    def execute_command(
        self, command: str, real_time: bool = False
    ) -> Optional[Tuple[str, str, int]]:
        """
        執行單一指令

        Args:
            command: 要執行的指令

        Returns:
            (output, error, exit_status) 元組，發生錯誤時返回 None
        """
        if self.persistent_session:
            output = self._executor.execute_in_session(command)
            self.output_handler.print_output(output)
            return output, "", 0
        else:
            if real_time:
                self._executor.execute_realtime(command)
                return None
            else:
                output, error, exit_status = self._executor.execute_simple(command)
                self.output_handler.print_output(output)
                return output, error, exit_status

    def close(self) -> None:
        """關閉 SSH 連接"""
        if self._executor and self._executor.is_session_active():
            self._executor.stop_session()
        self.connection_manager.close()
        self.output_handler.close()
        self._executor = None

    def __enter__(self):
        """支持 with 語句"""
        # 默認不啟用 persistent_session，保持向後兼容
        self.connect(persistent_session=False)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持 with 語句"""
        self.close()
        return False
