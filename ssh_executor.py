#!/usr/bin/env python3
"""SSH connection and shell script execution"""

import argparse
import paramiko
# import signal  # Temporarily disabled due to conflict with multi-threading
import sys
from typing import Tuple, Optional
from config import Config
from output_handler import OutputHandler


class SSHConnectionManager:
    """SSH Connection Manager"""

    def __init__(self, host: str, port: int, user: str, password: str):
        """
        Initialize SSH Connection Manager

        Args:
            host: Host address
            port: Port number
            user: Username
            password: Password
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self._client: Optional[paramiko.SSHClient] = None

    def connect(self) -> None:
        """Establish SSH connection"""
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        print(f"Connecting to {self.user}@{self.host}:{self.port}...")

        self._client.connect(
            hostname=self.host,
            port=self.port,
            username=self.user,
            password=self.password,
        )

        print("Connection successful!")

    def close(self) -> None:
        """Close SSH connection"""
        if self._client:
            self._client.close()
            print("SSH connection closed")
            self._client = None

    def is_connected(self) -> bool:
        """Check if connected"""
        return self._client is not None

    def get_client(self) -> paramiko.SSHClient:
        """Get SSH client"""
        if not self._client:
            raise Exception("SSH connection not established")
        return self._client

    def __enter__(self):
        """Support with statement"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support with statement"""
        self.close()
        return False


class ScriptReader:
    """Script Reader"""

    @staticmethod
    def read_script(script_path: str) -> str:
        """
        Read script file content

        Args:
            script_path: Path to script file

        Returns:
            Script content
        """
        with open(script_path, "r", encoding="utf-8") as f:
            return f.read()


class SignalHandler:
    """Signal Handler"""

    def __init__(self):
        self.interrupted = False
        self._original_handler = None

    def setup(self, stdin) -> None:
        """
        Setup signal handler

        Args:
            stdin: SSH standard input stream
        """
        # Temporarily disabled due to conflict with multi-threading
        # def handler(sig, frame):
        #     print("\n\nInterrupt signal received, stopping remote program...")
        #     try:
        #         stdin.write("\x03")
        #         stdin.flush()
        #     except Exception:
        #         pass
        #     self.interrupted = True

        # self._original_handler = signal.signal(signal.SIGINT, handler)
        # print("Tip: Press Ctrl+C to stop program execution\n")
        pass

    def stop(self) -> None:
        """Mark as interrupted"""
        self.interrupted = True

    def restore(self) -> None:
        """Restore original signal handler"""
        # Temporarily disabled due to conflict with multi-threading
        # if self._original_handler:
        #     signal.signal(signal.SIGINT, self._original_handler)
        pass


class RealTimeStreamReader:
    """Real-time Stream Reader"""

    def __init__(
        self,
        stdout,
        stderr,
        signal_handler: SignalHandler,
        output_handler: OutputHandler,
    ):
        """
        Initialize real-time stream reader

        Args:
            stdout: Standard output stream
            stderr: Standard error stream
            signal_handler: Signal handler
            output_handler: Output handler
        """
        self.stdout = stdout
        self.stderr = stderr
        self.signal_handler = signal_handler
        self.output_handler = output_handler

    def read(self) -> None:
        """Read and print output in real-time"""
        try:
            # Read output in real-time
            while not self.stdout.channel.exit_status_ready():
                if self.signal_handler.interrupted:
                    self._read_remaining()
                    break
                if self.stdout.channel.recv_ready():
                    output = self.stdout.channel.recv(1024).decode("utf-8")
                    self.output_handler.write(output, end="", flush=True)

            # Read remaining output
            if not self.signal_handler.interrupted:
                self._read_remaining()

            # Read error output
            error = self.stderr.read().decode("utf-8")
            if error:
                self.output_handler.print_error(error)

        except Exception as e:
            self.output_handler.write(f"\nError occurred during execution: {e}")

    def _read_remaining(self) -> None:
        """Read remaining output"""
        remaining = self.stdout.read().decode("utf-8")
        if remaining:
            self.output_handler.write(remaining, end="", flush=True)


class CommandExecutor:
    """Command Executor"""

    def __init__(self, ssh_client: paramiko.SSHClient, output_handler: OutputHandler):
        """
        Initialize command executor

        Args:
            ssh_client: SSH client
            output_handler: Output handler
        """
        self.ssh_client = ssh_client
        self.output_handler = output_handler
        self._shell = None
        self._session_active = False

    def execute_simple(self, command: str) -> Tuple[str, str, int]:
        """
        Execute simple command (waits for completion)

        Args:
            command: Command to execute

        Returns:
            (output, error, exit_status) tuple
        """
        stdin, stdout, stderr = self.ssh_client.exec_command(command)

        output = stdout.read().decode("utf-8")
        error = stderr.read().decode("utf-8")
        exit_status = stdout.channel.recv_exit_status()

        return output, error, exit_status

    def execute_realtime(self, command: str) -> None:
        """
        Execute command with real-time output

        Args:
            command: Command to execute
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
        Start a persistent interactive shell session
        """
        if self._session_active:
            return

        self._shell = self.ssh_client.invoke_shell()
        self._session_active = True

        # Wait for initial prompt and clear welcome message
        import time
        time.sleep(0.5)
        if self._shell.recv_ready():
            self._shell.recv(4096)

    def stop_session(self) -> None:
        """
        Stop persistent interactive shell session
        """
        if self._shell:
            self._shell.close()
            self._shell = None
            self._session_active = False

    def execute_in_session(self, command: str, timeout: float = 10.0) -> str:
        """
        Execute command in persistent session

        Args:
            command: Command to execute
            timeout: Timeout in seconds for waiting for output

        Returns:
            Command output
        """
        if not self._session_active:
            raise Exception("Session not started, please call start_session() first")

        import time
        import re

        # Matches common shell/CLI prompts at end of line:
        # e.g. "$ ", "# ", "> ", "APV# ", "APV(config)# "
        _PROMPT_RE = re.compile(r'[$#>]\s*$')

        # Send command
        self._shell.send(command + "\n")

        # Wait and collect output
        output = ""
        start_time = time.time()

        while True:
            if self._shell.recv_ready():
                chunk = self._shell.recv(4096).decode('utf-8')
                output += chunk

                # Strip ANSI escape codes before prompt detection
                clean = OutputHandler.clean_ansi(output)
                if _PROMPT_RE.search(clean.rstrip('\r\n').rstrip()):
                    break

            # Check timeout
            if time.time() - start_time > timeout:
                break

            time.sleep(0.1)

        return output

    def is_session_active(self) -> bool:
        """
        Check if session is active

        Returns:
            True if session is active, else False
        """
        return self._session_active


class SSHExecutor:
    """SSH Executor class (high-level wrapper)"""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        log_path: Optional[str] = None,
    ):
        """
        Initialize SSH Executor

        Args:
            host: Host address
            port: Port number
            user: Username
            password: Password
            log_path: Path to output file, if None then output to stdout
        """
        self.connection_manager = SSHConnectionManager(
            host=host,
            port=port,
            user=user,
            password=password,
        )
        self.output_handler = OutputHandler(log_path)
        self._executor: Optional[CommandExecutor] = None
        self.persistent_session: bool = True

    def connect(self, persistent_session: bool = False) -> None:
        """
        Establish SSH connection

        Args:
            persistent_session: Whether to enable persistent session to maintain state (e.g., directory, environment variables) between commands
        """
        self.connection_manager.connect()
        self._executor = CommandExecutor(
            self.connection_manager.get_client(), self.output_handler
        )
        self.persistent_session = persistent_session
        if persistent_session:
            self._executor.start_session()
    def connect_session(self) -> None:
        """Establish persistent SSH connection"""
        self.connect(persistent_session=True)
        
    def execute_script(
        self, script_path: str, real_time: bool = False
    ) -> Optional[Tuple[str, str, int]]:
        """
        Execute specified shell script

        Args:
            script_path: Path to shell script
            real_time: Whether to output in real-time (default: False)

        Returns:
            If real_time=False, returns (output, error, exit_status), else returns None
        """
        if not self._executor:
            raise Exception("SSH connection not established")

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
        Execute single command

        Args:
            command: Command to execute

        Returns:
            (output, error, exit_status) tuple, returns None on error
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
        """Close SSH connection"""
        if self._executor and self._executor.is_session_active():
            self._executor.stop_session()
        self.connection_manager.close()
        self.output_handler.close()
        self._executor = None

    def __enter__(self):
        """Support with statement"""
        # Default to not enabling persistent_session to maintain backward compatibility
        self.connect(persistent_session=False)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support with statement"""
        self.close()
        return False
