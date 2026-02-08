#!/usr/bin/env python3
"""Output Handler Module - Supports output to stdout or file"""

from typing import Optional
import os
import re


class OutputHandler:
    """Output Handler - Supports output to stdout or file"""

    @staticmethod
    def clean_ansi(text: str) -> str:
        """
        Remove ANSI escape sequences and terminal control characters

        Args:
            text: Text containing ANSI control characters

        Returns:
            Cleaned plain text
        """
        ansi_escape = re.compile(r'\x1b\[[0-9;]*[mGKHJF]|\r|\x1b\[\?[0-9]*[hl]')
        return ansi_escape.sub('', text)

    def __init__(self, output_path: Optional[str] = None):
        """
        Initialize Output Handler

        Args:
            output_path: Path to the output file, if None then output to stdout
        """
        self.output_path = output_path
        self._file_handle = None

        # If an output file is specified, open the file
        if self.output_path:
            try:
                # If the directory does not exist, create it
                output_dir = os.path.dirname(self.output_path)
                if output_dir and not os.path.exists(output_dir):
                    os.makedirs(output_dir, exist_ok=True)
                
                self._file_handle = open(self.output_path, 'w+', encoding='utf-8')
                print(f"Output will be written to file: {self.output_path}")
            except Exception as e:
                print(f"Warning: Unable to open output file {self.output_path}: {e}")
                print("Switching output to stdout")
                self._file_handle = None

    def write(self, message: str, end: str = '\n', flush: bool = False) -> None:
        """
        Write message to output target

        Args:
            message: Message to output
            end: End character (default is newline)
            flush: Whether to immediately flush the buffer
        """
        message = self.clean_ansi(message)
        if self._file_handle:
            self._file_handle.write(message + end)
            # print(f"OUTPUT<==\t{message}", end=end, flush=flush)
            if flush:
                self._file_handle.flush()
        else:
            print(f"{message}", end=end, flush=flush)

    def print_header(self, script_path: str) -> None:
        """Print execution header information"""
        self.write(f"\nStarting execution of commands in {script_path}...\n")
        self.write("-" * 50)

    def print_footer(self, interrupted: bool = False) -> None:
        """Print execution footer information"""
        self.write("-" * 50)
        if interrupted:
            self.write("\nProgram interrupted by user")
        else:
            self.write("\nExecution completed")

    def print_exit_status(self, exit_status: int) -> None:
        """Print exit status"""
        self.write(f"\nExecution completed, exit status code: {exit_status}")

    def print_output(self, output: str, prefix: str = "Execution Results") -> None:
        """Print standard output"""
        if output:
            self.write(f"{prefix}:")
            self.write(output)

    def print_error(self, error: str) -> None:
        """Print error output"""
        if error:
            self.write(f"\nError output:\n{error}")

    def close(self) -> None:
        """Close output file (if opened)"""
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None

    def __enter__(self):
        """Support with statement"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support with statement"""
        self.close()
        return False
