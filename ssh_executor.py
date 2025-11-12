#!/usr/bin/env python3
"""SSH 連接並執行 shell 腳本"""

import argparse
import paramiko
import signal
import sys
from config import Config


class SSHExecutor:
    """SSH 執行器類別"""

    def __init__(self, config):
        """
        初始化 SSH 執行器

        Args:
            config: Config 物件，包含連接資訊
        """
        self.host = config.HOST
        self.port = config.PORT
        self.user = config.USER
        self.password = config.PASSWORD
        self.ssh_client = None

    def connect(self):
        """建立 SSH 連接"""
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        print(f"正在連接到 {self.user}@{self.host}:{self.port}...")

        self.ssh_client.connect(
            hostname=self.host,
            port=self.port,
            username=self.user,
            password=self.password
        )

        print("連接成功！")

    def execute_script(self, script_path, real_time=False):
        """
        執行指定的 shell 腳本

        Args:
            script_path: shell 腳本的路徑
            real_time: 是否即時輸出 (預設: False)

        Returns:
            tuple: (output, error, exit_status)
        """
        if not self.ssh_client:
            raise Exception("尚未建立 SSH 連接")

        # 讀取腳本內容
        with open(script_path, 'r', encoding='utf-8') as f:
            commands = f.read()

        print(f"\n開始執行 {script_path} 中的指令...\n")
        print("-" * 50)

        if real_time:
            # 即時輸出模式
            stdin, stdout, stderr = self.ssh_client.exec_command(commands, get_pty=True)

            # 用於標記是否被中斷
            interrupted = False

            # 設定 Ctrl+C 處理
            def signal_handler(sig, frame):
                nonlocal interrupted
                print("\n\n收到中斷信號，正在停止遠端程式...")
                # 發送 Ctrl+C 到遠端
                try:
                    stdin.write('\x03')
                    stdin.flush()
                except:
                    pass
                interrupted = True

            original_handler = signal.signal(signal.SIGINT, signal_handler)

            print("提示: 按 Ctrl+C 可停止程式執行\n")

            try:
                # 即時讀取輸出
                while not stdout.channel.exit_status_ready():
                    if interrupted:
                        break
                    if stdout.channel.recv_ready():
                        output = stdout.channel.recv(1024).decode('utf-8')
                        print(output, end='', flush=True)

                # 讀取剩餘輸出
                if not interrupted:
                    remaining = stdout.read().decode('utf-8')
                    if remaining:
                        print(remaining, end='', flush=True)

                # 讀取錯誤輸出
                error = stderr.read().decode('utf-8')
                if error:
                    print(f"\n錯誤輸出：\n{error}")

                if interrupted:
                    print("\n程式已被使用者中斷")
                    print("-" * 50)
                else:
                    print("-" * 50)
                    print(f"\n執行完成")

            except Exception as e:
                print(f"\n執行過程中發生錯誤：{e}")
            finally:
                # 恢復原始的信號處理器
                signal.signal(signal.SIGINT, original_handler)
        else:
            # 原有的等待執行完畢模式
            # 執行指令
            stdin, stdout, stderr = self.ssh_client.exec_command(commands)

            # 獲取執行結果
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            exit_status = stdout.channel.recv_exit_status()

            # 顯示輸出
            if output:
                print("執行結果：")
                print(output)

            if error:
                print("錯誤訊息：")
                print(error)

            print("-" * 50)
            print(f"\n執行完成，退出狀態碼：{exit_status}")

            return output, error, exit_status

    def close(self):
        """關閉 SSH 連接"""
        if self.ssh_client:
            self.ssh_client.close()
            print("SSH 連接已關閉")

