#!/usr/bin/env python3
"""輸出處理器模組 - 支援輸出到 stdout 或檔案"""

from typing import Optional


class OutputHandler:
    """輸出處理器 - 支援輸出到 stdout 或檔案"""

    def __init__(self, output_path: Optional[str] = None):
        """
        初始化輸出處理器

        Args:
            output_path: 輸出檔案路徑，若為 None 則輸出到 stdout
        """
        self.output_path = output_path
        self._file_handle = None

        # 如果指定了輸出檔案，開啟檔案
        if self.output_path:
            try:
                self._file_handle = open(self.output_path, 'w', encoding='utf-8')
                print(f"輸出將寫入到檔案: {self.output_path}")
            except Exception as e:
                print(f"警告：無法開啟輸出檔案 {self.output_path}: {e}")
                print("將改為輸出到 stdout")
                self._file_handle = None

    def write(self, message: str, end: str = '\n', flush: bool = False) -> None:
        """
        寫入訊息到輸出目標

        Args:
            message: 要輸出的訊息
            end: 結尾字符（預設為換行）
            flush: 是否立即刷新緩衝區
        """
        if self._file_handle:
            self._file_handle.write(message + end)
            print(f"OUTPUT<==\t{message}", end=end, flush=flush)
            if flush:
                self._file_handle.flush()
        else:
            print(f"STDOUT<==\t{message}", end=end, flush=flush)

    def print_header(self, script_path: str) -> None:
        """打印執行頭部信息"""
        self.write(f"\n開始執行 {script_path} 中的指令...\n")
        self.write("-" * 50)

    def print_footer(self, interrupted: bool = False) -> None:
        """打印執行尾部信息"""
        self.write("-" * 50)
        if interrupted:
            self.write("\n程式已被使用者中斷")
        else:
            self.write("\n執行完成")

    def print_exit_status(self, exit_status: int) -> None:
        """打印退出狀態"""
        self.write(f"\n執行完成，退出狀態碼：{exit_status}")

    def print_output(self, output: str, prefix: str = "執行結果") -> None:
        """打印標準輸出"""
        if output:
            self.write(f"{prefix}：")
            self.write(output)

    def print_error(self, error: str) -> None:
        """打印錯誤輸出"""
        if error:
            self.write(f"\n錯誤輸出：\n{error}")

    def close(self) -> None:
        """關閉輸出檔案（如果有開啟）"""
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None

    def __enter__(self):
        """支持 with 語句"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持 with 語句"""
        self.close()
        return False
