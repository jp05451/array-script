# Array Script - DPerf Test Automation Tool
繁體中文: [README_zh-TW.md](README_zh-TW.md)

This project provides automated scripts to run DPerf network performance tests. It connects to remote hosts via SSH, configures the DPDK environment, and executes tests automatically.

## Table of Contents

- [Core Module Overview](#core-module-overview)
  - [1. dperfSetup.py](#1-dperfsetuppy)
  - [2. ssh_executor.py](#2-ssh_executorpy)
  - [3. output_handler.py](#3-output_handlerpy)
  - [4. RedisDB.py](#4-redisdbpy)
  - [5. config.py](#5-configpy)
  - [6. APVSetup.py](#6-apvsetuppy)
  - [7. Additional dperfSetup.py Methods](#7-additional-dperfsetuppy-methods)
  - [8. scan_functions.py](#8-scan_functionspy)
  - [9. system_monitor.py](#9-system_monitorpy)
  - [10. trafficGenerator.py](#10-trafficgeneratorpy)
- [Usage Examples](#usage-examples)
  - [Basic Usage](#basic-usage)
  - [SSH Command Execution](#ssh-command-execution)
  - [Custom Output Handling](#custom-output-handling)
- [Configuration Guide (config.yaml)](#configuration-guide-configyaml)
  - [Basic Structure](#basic-structure)
  - [Main Configuration Blocks](#main-configuration-blocks)
  - [Configuration Recommendations](#configuration-recommendations)
  - [Multiple Pair Configuration](#multiple-pair-configuration)
- [System Requirements](#system-requirements)
- [Notes](#notes)
- [Project Function Scan Results](#project-function-scan-results)

## Core Module Overview

### 1. dperfSetup.py

This module is responsible for the full DPerf test setup and execution workflow.

<details>
<summary><b>Class: dperf</b></summary>

The main controller class for DPerf tests, managing the full test lifecycle.

##### Initialization
```python
__init__(self, config: Config, pair_index: int = 0, log_path: str = None, output_path: str = None)
```
- **Purpose**: Initialize a DPerf test instance
- **Parameters**:
  - `config`: Configuration object containing all test parameters
  - `pair_index`: Pair index used to identify different NIC pairs
  - `log_path`: Log file path (default: `./logs/dperf_pair{pair_index}.log`)
  - `output_path`: Output file path for results
- **Notes**: Creates three SSH executors (management, server, client) and initializes test parameters

##### Main Methods

###### `connect()`
- **Purpose**: Establish SSH connections to remote hosts
- **Notes**: Uses persistent session mode

###### `disconnect()`
- **Purpose**: Close SSH connections

###### `runPairTest()`
- **Purpose**: Run a full DPerf test workflow
- **Returns**: Dictionary containing server and client results
- **Flow**:
  1. Set up environment (hugepages, bind NICs, generate config)
  2. Start server and client test threads simultaneously
  3. Wait for completion and collect results
  4. Output results to CSV

###### `outputResults()`
- **Purpose**: Output test results to CSV
- **Format**: CSV with Metric, Server, Client columns
- **Notes**: Creates output directory if missing and writes parsed metrics

###### `serverStart()`
- **Purpose**: Start DPerf server in a separate thread and collect traffic metrics
- **Flow**:
  1. Establish SSH connection
  2. Switch to dperf directory
  3. Execute server test script
  4. Parse output
  5. Disconnect

###### `clientStart()`
- **Purpose**: Start DPerf client in a separate thread and collect traffic metrics
- **Flow**: Similar to `serverStart()` but for the client side

###### `parseOutput(log)`
- **Purpose**: Parse DPerf output logs
- **Parameter**: `log` - output log string
- **Returns**: Dictionary of metrics
- **Notes**:
  - Remove ANSI escape sequences
  - Find the “Total Numbers” block
  - Parse into key-value pairs

###### `bindNICs()`
- **Purpose**: Bind NICs to the DPDK driver
- **Notes**:
  1. Bring down network interfaces
  2. Bind NICs to vfio-pci via dpdk-devbind.py
  3. Use no-iommu mode

###### `unbindNICs()`
- **Purpose**: Unbind NICs and restore native drivers
- **Notes**:
  1. Bind back to native drivers
  2. Bring network interfaces up
  3. Show binding status

###### `setHugePages()`
- **Purpose**: Configure hugepages
- **Notes**: Uses values from the config file

###### `setupConfig()`
- **Purpose**: Generate and upload DPerf config files
- **Notes**:
  - Create config directory if missing
  - Generate server/client configs
  - Upload to remote host

###### `setupEnv()`
- **Purpose**: Set up the full DPerf test environment
- **Flow**:
  1. Connect via SSH
  2. Set hugepages
  3. Bind NICs
  4. Create config files
  5. Disconnect

###### `generateServerConfig()`
- **Purpose**: Generate DPerf server config content
- **Returns**: Config file string
- **Fields**: mode, tx_burst, cpu, rss, socket_mem, protocol, duration, payload_size, keepalive, port, client, server, listen, etc.

###### `generateClientConfig()`
- **Purpose**: Generate DPerf client config content
- **Returns**: Config file string
- **Fields**: mode, tx_burst, launch_num, cpu, rss, socket_mem, protocol, payload_size, duration, cc, keepalive, port, client, server, listen, etc.

</details>

---

### 2. ssh_executor.py

This module provides SSH connection management and remote command execution.

<details>
<summary><b>Class: SSHConnectionManager</b></summary>

Manages SSH connections.

##### Initialization
```python
__init__(self, host: str, port: int, user: str, password: str)
```
- **Purpose**: Initialize SSH connection manager
- **Parameters**:
  - `host`: Host address
  - `port`: SSH port
  - `user`: Username
  - `password`: Password

##### Main Methods

###### `connect()`
- **Purpose**: Establish SSH connection
- **Notes**: Uses paramiko and auto-accepts host keys

###### `close()`
- **Purpose**: Close SSH connection

###### `is_connected()`
- **Purpose**: Check if connected
- **Returns**: Boolean

###### `get_client()`
- **Purpose**: Get SSH client instance
- **Returns**: paramiko.SSHClient

###### `__enter__()` / `__exit__()`
- **Purpose**: Context manager support

</details>

---

<details>
<summary><b>Class: ScriptReader</b></summary>

Reads local script files.

##### Static Method

###### `read_script(script_path: str)`
- **Purpose**: Read script content
- **Parameter**: `script_path` - script path
- **Returns**: Script content string

</details>

---

<details>
<summary><b>Class: SignalHandler</b></summary>

Signal handler for interruption signals (currently disabled to avoid multi-thread conflicts).

##### Methods

###### `setup(stdin)`
- **Purpose**: Set up signal handling
- **Parameter**: `stdin` - SSH stdin
- **Notes**: Empty implementation reserved for future use

###### `stop()`
- **Purpose**: Mark as interrupted

###### `restore()`
- **Purpose**: Restore original signal handler

</details>

---

<details>
<summary><b>Class: RealTimeStreamReader</b></summary>

Reads command output in real time.

##### Initialization
```python
__init__(self, stdout, stderr, signal_handler: SignalHandler, output_handler: OutputHandler)
```
- **Parameters**:
  - `stdout`: Standard output stream
  - `stderr`: Standard error stream
  - `signal_handler`: SignalHandler instance
  - `output_handler`: OutputHandler instance

##### Main Methods

###### `read()`
- **Purpose**: Read and print command output in real time
- **Notes**:
  - Continues until command completes
  - Supports interruption
  - Separately handles stdout and stderr

###### `_read_remaining()`
- **Purpose**: Read remaining output (private)

</details>

---

<details>
<summary><b>Class: CommandExecutor</b></summary>

Executes commands on remote hosts.

##### Initialization
```python
__init__(self, ssh_client: paramiko.SSHClient, output_handler: OutputHandler)
```
- **Parameters**:
  - `ssh_client`: SSH client instance
  - `output_handler`: OutputHandler instance

##### Main Methods

###### `execute_simple(command: str)`
- **Purpose**: Execute command and wait for completion
- **Parameter**: `command`
- **Returns**: `(output, error, exit_status)`

###### `execute_realtime(command: str)`
- **Purpose**: Execute command and stream output
- **Parameter**: `command`

###### `start_session()`
- **Purpose**: Start persistent interactive shell session
- **Notes**: Keeps state across commands (cwd, env, etc.)

###### `stop_session()`
- **Purpose**: Stop persistent session

###### `execute_in_session(command: str, timeout: float = 10.0)`
- **Purpose**: Execute in persistent session
- **Parameters**:
  - `command`
  - `timeout` (seconds)
- **Returns**: Output string

###### `is_session_active()`
- **Purpose**: Check if session is active
- **Returns**: Boolean

</details>

---

<details>
<summary><b>Class: SSHExecutor</b></summary>

High-level SSH executor that wraps all SSH features.

##### Initialization
```python
__init__(self, host: str, port: int, user: str, password: str, log_path: Optional[str] = None)
```
- **Parameters**:
  - `host`: Host address
  - `port`: SSH port
  - `user`: Username
  - `password`: Password
  - `log_path`: Log file path (if None, output to stdout)

##### Main Methods

###### `connect(persistent_session: bool = False)`
- **Purpose**: Establish SSH connection
- **Parameter**: `persistent_session` - enable persistent session
- **Notes**: Persistent sessions keep state across commands

###### `connect_session()`
- **Purpose**: Shortcut for `connect(persistent_session=True)`

###### `execute_script(script_path: str, real_time: bool = False)`
- **Purpose**: Execute a local shell script
- **Parameters**:
  - `script_path`
  - `real_time`
- **Returns**:
  - If `real_time=False`: `(output, error, exit_status)`
  - If `real_time=True`: None

###### `execute_command(command: str, real_time: bool = False)`
- **Purpose**: Execute a single command
- **Parameters**:
  - `command`
  - `real_time`
- **Returns**:
  - If `real_time=False`: `(output, error, exit_status)`
  - If `real_time=True`: None
- **Notes**: Uses persistent session when enabled

###### `close()`
- **Purpose**: Close SSH connection and clean up resources
- **Notes**: Stops session (if active), closes connection, closes output handler

###### `__enter__()` / `__exit__()`
- **Purpose**: Context manager support

</details>

---

### 3. output_handler.py

This module provides output handling to stdout or files.

<details>
<summary><b>Class: OutputHandler</b></summary>

Unified output handler.

##### Initialization
```python
__init__(self, output_path: Optional[str] = None)
```
- **Purpose**: Initialize output handler
- **Parameter**: `output_path` - output file path (if None, output to stdout)
- **Notes**:
  - Creates output directory if missing
  - Opens file for writing
  - Falls back to stdout if file open fails

##### Static Method

###### `clean_ansi(text: str)` (staticmethod)
- **Purpose**: Remove ANSI escape sequences and terminal control characters
- **Parameter**: `text` - input text with ANSI sequences
- **Returns**: Clean text
- **Notes**: Removes color codes and cursor controls

##### Main Methods

###### `write(message: str, end: str = '\n', flush: bool = False)`
- **Purpose**: Write a message to output
- **Parameters**:
  - `message`
  - `end`
  - `flush`
- **Notes**: Automatically removes ANSI sequences

###### `print_header(script_path: str)`
- **Purpose**: Print header info
- **Parameter**: `script_path` - script path
- **Output Format**:
  ```
  Start executing commands from {script_path}...
  --------------------------------------------------
  ```

###### `print_footer(interrupted: bool = False)`
- **Purpose**: Print footer info
- **Parameter**: `interrupted` - whether interrupted
- **Output Format**:
  ```
  --------------------------------------------------
  Execution completed / Execution interrupted by user
  ```

###### `print_exit_status(exit_status: int)`
- **Purpose**: Print exit status
- **Parameter**: `exit_status`

###### `print_output(output: str, prefix: str = "Execution Result")`
- **Purpose**: Print standard output
- **Parameters**:
  - `output`
  - `prefix`

###### `print_error(error: str)`
- **Purpose**: Print error output
- **Parameter**: `error`

###### `close()`
- **Purpose**: Close output file
- **Notes**: Closes file handle if opened

###### `__enter__()` / `__exit__()`
- **Purpose**: Context manager support
- **Notes**: Ensures resources are released

</details>

---

### 4. RedisDB.py

This module provides Redis database operations to store and retrieve test monitoring data.

<details>
<summary><b>Class: RedisHandler</b></summary>

Redis database handler for persisting test data.

##### Initialization
```python
__init__(self, host: str = "localhost", port: int = 6379, db: int = 0, password: Optional[str] = None, decode_responses: bool = True)
```
- **Purpose**: Initialize Redis connection
- **Parameters**:
  - `host`: Redis host (default: localhost)
  - `port`: Redis port (default: 6379)
  - `db`: Redis DB index (default: 0)
  - `password`: Redis password (optional)
  - `decode_responses`: decode responses to strings (default: True)
- **Notes**: Automatically tests connection and prints status

##### Main Methods

###### `is_connected()`
- **Purpose**: Check if Redis is connected
- **Returns**: Boolean

###### `save_monitor_data(pair_index: int, timestamp: str, cpu_usage: float, ram_used: int, ram_total: int, ram_usage: float)`
- **Purpose**: Save monitoring data
- **Parameters**:
  - `pair_index`
  - `timestamp` (format: '%Y-%m-%d %H:%M:%S')
  - `cpu_usage`
  - `ram_used` (MB)
  - `ram_total` (MB)
  - `ram_usage`
- **Returns**: True on success, otherwise False
- **Data Structure**:
  - Key: `monitor:pair{index}:{timestamp}`
  - Sorted set by time: `monitor:pair{index}:timeline`

###### `save_test_output(pair_index: int, role: str, output: Dict, timestamp: Optional[str] = None)`
- **Purpose**: Save test output (server or client)
- **Parameters**:
  - `pair_index`
  - `role` ('server' or 'client')
  - `output` (dict)
  - `timestamp` (optional; defaults to now)
- **Returns**: True on success, otherwise False
- **Data Structure**:
  - Info Key: `test:pair{index}:{role}:{timestamp}:info`
  - Metrics Key: `test:pair{index}:{role}:{timestamp}:metrics`

###### `get_monitor_data(pair_index: int, start_time: Optional[str] = None, end_time: Optional[str] = None)`
- **Purpose**: Get monitoring data
- **Parameters**:
  - `pair_index`
  - `start_time` (optional)
  - `end_time` (optional)
- **Returns**: List of monitoring data

###### `get_test_output(pair_index: int, role: str, timestamp: Optional[str] = None, include_metrics: bool = True)`
- **Purpose**: Get test output
- **Parameters**:
  - `pair_index`
  - `role` ('server' or 'client')
  - `timestamp` (optional; if omitted, returns latest)
  - `include_metrics` (default: True)
- **Returns**: Dict with 'info' and 'metrics'

###### `clear_pair_data(pair_index: int)`
- **Purpose**: Clear all data for a pair
- **Parameter**: `pair_index`
- **Returns**: True on success, otherwise False
- **Notes**: Deletes all monitoring and test output for the pair

###### `get_all_test_outputs(pair_index: int, role: str, start_time: Optional[str] = None, end_time: Optional[str] = None, include_metrics: bool = True)`
- **Purpose**: Get all test outputs in a time range
- **Parameters**:
  - `pair_index`
  - `role` ('server' or 'client')
  - `start_time` (optional)
  - `end_time` (optional)
  - `include_metrics`
- **Returns**: List of test outputs

###### `get_specific_metrics(pair_index: int, role: str, metric_names: List[str], timestamp: Optional[str] = None)`
- **Purpose**: Get specific metrics
- **Parameters**:
  - `pair_index`
  - `role` ('server' or 'client')
  - `metric_names` (e.g. ['duration', 'ackDup'])
  - `timestamp` (optional; if omitted, returns latest)
- **Returns**: Dict of specified metrics

###### `get_pair_summary(pair_index: int)`
- **Purpose**: Get summary for a pair
- **Parameter**: `pair_index`
- **Returns**: Summary dict:
  - `pair_index`
  - `monitor_count`
  - `server_output_count`
  - `client_output_count`

###### `close()`
- **Purpose**: Close Redis connection
- **Notes**: Releases connection resources

</details>

---

### 5. config.py

This module provides configuration management using dataclasses.

<details>
<summary><b>Dataclasses</b></summary>

##### `Client`
- **Purpose**: Basic client config
- **Fields**:
  - `nic_pci: str`: NIC PCI address
  - `ip: str`: IP address
  - `gw: str`: Gateway address

##### `ClientConfig`
- **Purpose**: Detailed client config
- **Fields**:
  | Field | Type | Default | Description |
  |------|------|---------|-------------|
  | `client_nic_pci` | str | "" | NIC PCI address |
  | `client_nic_name` | str | "" | NIC interface name |
  | `client_nic_driver` | str | "i40e" | NIC driver |
  | `client_ip` | str | "" | Client IP |
  | `source_ip_nums` | int | 0 | Number of simulated source IPs |
  | `client_gw` | str | "" | Client gateway |
  | `client_duration` | str | "" | Test duration |
  | `client_cpu_core` | int | 0 | CPU cores |
  | `tx_burst` | int | 0 | TX burst size |
  | `launch_num` | int | 0 | Number of launched sessions |
  | `cc` | str | "" | Concurrent connections |
  | `keepalive` | str | "" | Keepalive interval |
  | `rss` | bool | False | Enable RSS |
  | `socket_mem` | int | 0 | Memory pool size |
  | `virtual_server_ip` | str | "" | Target server IP |
  | `virtual_server_port` | int | 0 | Target server port |
  | `virtual_server_port_nums` | int | 1 | Number of server ports |

##### `ServerConfig`
- **Purpose**: Detailed server config
- **Fields**:
  | Field | Type | Default | Description |
  |------|------|---------|-------------|
  | `server_nic_pci` | str | "" | NIC PCI address |
  | `server_nic_name` | str | "" | NIC interface name |
  | `server_nic_driver` | str | "i40e" | NIC driver |
  | `server_ip` | str | "" | Server IP |
  | `server_gw` | str | "" | Server gateway |
  | `server_duration` | str | "" | Test duration |
  | `server_cpu_core` | int | 0 | CPU cores |
  | `tx_burst` | int | 0 | TX burst size |
  | `keepalive` | str | "" | Keepalive interval |
  | `rss` | bool | False | Enable RSS |
  | `socket_mem` | int | 0 | Memory pool size |
  | `listen_port` | int | 0 | Listen port |
  | `listen_port_nums` | int | 1 | Number of listen ports |

##### `TrafficGeneratorPair`
- **Purpose**: Traffic generator pair configuration
- **Fields**:
  - `client: ClientConfig`
  - `server: ServerConfig`
  - `payload_size: int` (default: 0)
  - `protocol: str` (default: "tcp")

##### `TrafficGenerator`
- **Purpose**: Traffic generator configuration
- **Fields**:
  - `management_ip: str`
  - `management_port: int`
  - `username: str`
  - `password: str`
  - `dpdk_path: str`
  - `dperf_path: str`
  - `hugepage_frames: int` (default: 2)
  - `hugepage_size: str` (default: "1G")
  - `pairs: List[TrafficGeneratorPair]`

##### `TestConfig`
- **Purpose**: Test configuration
- **Fields**:
  - `apv_management_ip: str`
  - `apv_management_port: int`
  - `apv_username: str`
  - `apv_password: str`
  - `apv_enable_password: str`
  - `traffic_generator: TrafficGenerator`

</details>

<details>
<summary><b>Class: Config</b></summary>

Main configuration class for loading and managing all configs.

##### Initialization
```python
__init__(self, yaml_path: str = None)
```
- **Purpose**: Initialize config
- **Parameter**: `yaml_path` - YAML config file path (optional; if provided, auto-load)

##### Main Methods

###### `from_yaml(yaml_path: str)`
- **Purpose**: Load config from YAML
- **Parameter**: `yaml_path`
- **Returns**: self (supports chaining)
- **Notes**: Parses YAML and builds dataclass objects

###### `to_dict()`
- **Purpose**: Convert config to dict
- **Returns**: `Dict[str, Any]`
- **Notes**: Converts all dataclasses into serializable dicts

</details>

---

### 6. APVSetup.py

This module manages APV load balancer setup.

<details>
<summary><b>Class: APVSetup</b></summary>

APV load balancer configuration class for setting up load balancing rules for multiple protocols.

##### Initialization
```python
__init__(self, config: Config, log_path: str = 'logs')
```
- **Purpose**: Initialize APV setup
- **Parameters**:
  - `config`: Config object
  - `log_path`: Log path (default: 'logs')
- **Notes**: Extracts APV connection info and creates SSH executor

##### Main Methods

###### `connect()`
- **Purpose**: Connect to APV device via SSH
- **Notes**: Uses persistent session mode

###### `disconnect()`
- **Purpose**: Disconnect from APV device

###### `_execute_commands(commands: list, dry_run: bool = False)`
- **Purpose**: Execute a list of commands (private)
- **Parameters**:
  - `commands`: List of commands
  - `dry_run`: If True, print only
- **Notes**: Prints or executes commands depending on dry_run

###### `setupUDPLoadBalancer(pair_index: int, dry_run: bool = False, clear: bool = False)`
- **Purpose**: Configure UDP load balancer
- **Parameters**:
  - `pair_index`
  - `dry_run`
  - `clear`
- **Config Items**:
  - Real Server config
  - Virtual Server config
  - Load balance group (Round-Robin)
  - Policy binding

###### `setupTCPLoadBalancer(pair_index: int, dry_run: bool = False, clear: bool = False)`
- **Purpose**: Configure TCP load balancer
- **Parameters**: Same as `setupUDPLoadBalancer`
- **Notes**: Similar logic, but for TCP

###### `setupHTTPLoadBalancer(pair_index: int, dry_run: bool = False, clear: bool = False)`
- **Purpose**: Configure HTTP load balancer
- **Parameters**: Same as `setupUDPLoadBalancer`
- **Notes**: Similar logic, but for HTTP

###### `setupEnv(dry_run: bool = False, clear: bool = False)`
- **Purpose**: Configure APV environment
- **Parameters**:
  - `dry_run`
  - `clear`
- **Flow**:
  1. Enter enable mode
  2. Input enable password
  3. Enter config terminal
  4. Configure load balancer per pair and protocol
  5. Save configuration (write memory)

</details>

#### Standalone Function

###### `argParser()`
- **Purpose**: Parse command-line arguments
- **Returns**: Parsed args
- **Parameters**:
  - `--dry-run`: Simulate only
  - `--clear`: Clear load balancer settings
  - `-c, --config`: Config file path

---

### 7. Additional dperfSetup.py Methods

The following are additional methods in the `dperf` class (supplementing the above documentation):

##### Redis Integration Methods

###### `monitorStart()`
- **Purpose**: Start monitoring CPU and RAM usage
- **Notes**:
  - Records system usage once per second
  - Writes to local CSV and Redis (if enabled)
  - Runs in a separate thread

###### `monitorStop()`
- **Purpose**: Stop monitoring
- **Notes**: Sets monitoring flag to False

###### `get_redis_summary()`
- **Purpose**: Get summary for the pair from Redis
- **Returns**: Summary dict or None (if Redis not connected)

###### `get_redis_monitor_data(start_time=None, end_time=None)`
- **Purpose**: Get monitoring data from Redis
- **Parameters**:
  - `start_time` (optional)
  - `end_time` (optional)
- **Returns**: Monitoring data list

###### `get_redis_test_output(role: str)`
- **Purpose**: Get test output from Redis
- **Parameter**: `role` ('server' or 'client')
- **Returns**: Test output dict or None

##### Updated Initialization
```python
__init__(self, config: Config, pair_index: int = 0, log_path: str = None, output_path: str = None, redis_host: str = "localhost", redis_port: int = 6379, redis_db: int = 0, enable_redis: bool = True)
```
- **New Parameters**:
  - `redis_host`: Redis host (default: localhost)
  - `redis_port`: Redis port (default: 6379)
  - `redis_db`: Redis DB index (default: 0)
  - `enable_redis`: Enable Redis storage (default: True)

---

### 9. system_monitor.py

This module provides system resource monitoring for remote hosts to track CPU and RAM usage during tests.

<details>
<summary><b>Class: SystemMonitor</b></summary>

System monitor for remote host CPU/RAM usage. A single monitor instance can be shared by multiple pairs.

##### Initialization
```python
__init__(self, management_ip: str, management_port: int, username: str, password: str, log_path: str = "./logs", redis_host: str = "localhost", redis_port: int = 6379, redis_db: int = 0, enable_redis: bool = True)
```
- **Purpose**: Initialize system monitor
- **Parameters**:
  - `management_ip`: Remote host IP
  - `management_port`: SSH port
  - `username`: SSH username
  - `password`: SSH password
  - `log_path`: Log output path (default: `./logs`)
  - `redis_host`: Redis host (default: localhost)
  - `redis_port`: Redis port (default: 6379)
  - `redis_db`: Redis DB index (default: 0)
  - `enable_redis`: Enable Redis storage (default: True)

##### Main Methods

###### `connect()`
- **Purpose**: Connect to remote host via SSH

###### `disconnect()`
- **Purpose**: Disconnect from remote host

###### `start(output_file: str = None)`
- **Purpose**: Start monitoring in a new thread
- **Parameter**: `output_file` - output path (if None, uses default)
- **Notes**: Runs a separate thread to continuously record CPU/RAM

###### `stop()`
- **Purpose**: Stop monitoring
- **Notes**: Sets stop flag and waits for thread to end

###### `_monitor_loop(output_file: str = None)`
- **Purpose**: Monitoring loop (private)
- **Parameter**: `output_file`
- **Notes**: Records CPU/RAM once per second, writes to local CSV and Redis (if enabled)

###### `get_data()`
- **Purpose**: Get monitoring data
- **Returns**: List

###### `get_redis_monitor_data(start_time=None, end_time=None)`
- **Purpose**: Get monitoring data from Redis
- **Parameters**:
  - `start_time` (optional)
  - `end_time` (optional)
- **Returns**: List

###### `is_monitoring()`
- **Purpose**: Check if monitoring is running
- **Returns**: Boolean

</details>

---

### 10. trafficGenerator.py

This module provides a unified interface to manage multiple dperf pairs and a shared SystemMonitor.

<details>
<summary><b>Class: TrafficGenerator</b></summary>

Traffic generator manager that encapsulates multiple dperf pairs and a shared SystemMonitor.

##### Initialization
```python
__init__(self, config: Config, log_path: str = "./logs", output_path: str = "./results", redis_host: str = "localhost", redis_port: int = 6379, redis_db: int = 0, enable_redis: bool = True)
```
- **Purpose**: Initialize traffic generator with multiple pairs and a SystemMonitor
- **Parameters**:
  - `config`: Config object
  - `log_path`: Log output path (default: `./logs`)
  - `output_path`: Results output path (default: `./results`)
  - `redis_host`: Redis host (default: localhost)
  - `redis_port`: Redis port (default: 6379)
  - `redis_db`: Redis DB index (default: 0)
  - `enable_redis`: Enable Redis storage (default: True)

##### Main Methods

###### `connect()`
- **Purpose**: Connect to remote host
- **Notes**: Connects SystemMonitor and all dperf pairs

###### `disconnect()`
- **Purpose**: Disconnect all connections
- **Notes**: Disconnects all dperf pairs and SystemMonitor

###### `setup_env(pair_indices: list = None)`
- **Purpose**: Set up test environment
- **Parameter**: `pair_indices` - list of pair indices (if None, all pairs)
- **Notes**: Sets up DPDK environment for selected pairs in order

###### `run_test(pair_indices: list = None, enable_monitor: bool = True, parallel: bool = False, monitor_output_file: str = None)`
- **Purpose**: Run traffic tests
- **Parameters**:
  - `pair_indices`: list of pair indices (if None, all pairs)
  - `enable_monitor`: enable monitoring (default: True)
  - `parallel`: run in parallel (default: False)
  - `monitor_output_file`: monitor output path
- **Returns**: Results dict with each pair's server/client output and monitoring data
- **Notes**: Uses sequential or parallel mode based on `parallel`

###### `_run_sequential(pair_indices: list)`
- **Purpose**: Run tests sequentially (private)
- **Parameter**: `pair_indices`
- **Returns**: Results dict

###### `_run_parallel(pair_indices: list)`
- **Purpose**: Run tests in parallel (private)
- **Parameter**: `pair_indices`
- **Returns**: Results dict
- **Notes**: Uses threads to run multiple pairs in parallel

###### `get_pair(pair_index: int)`
- **Purpose**: Get a specific dperf pair instance
- **Parameter**: `pair_index`
- **Returns**: `dperf` instance or None

###### `get_monitor()`
- **Purpose**: Get SystemMonitor instance
- **Returns**: `SystemMonitor`

###### `get_pair_count()`
- **Purpose**: Get number of pairs
- **Returns**: Integer

</details>

---

## Usage Examples

### Basic Usage
```python
from config import Config
from dperfSetup import dperf

# Load config
config = Config()
config_data = config.from_yaml("config.yaml")

# Create test instance
test = dperf(config=config_data, pair_index=0)

# Set up environment
test.setupEnv()

# Run test
output = test.runPairTest()
print(output)
```

### SSH Command Execution
```python
from ssh_executor import SSHExecutor

# Create SSH executor
executor = SSHExecutor(
    host="192.168.1.100",
    port=22,
    user="admin",
    password="password",
    log_path="./logs/test.log"
)

# Use persistent session
executor.connect(persistent_session=True)
executor.execute_command("cd /home/user")
executor.execute_command("ls -la")
executor.close()
```

### Custom Output Handling
```python
from output_handler import OutputHandler

# Output to file
with OutputHandler(output_path="./output.txt") as handler:
    handler.write("Test started")
    handler.print_header("test_script.sh")
    handler.write("Running...")
    handler.print_footer()

# Output to stdout
handler = OutputHandler()
handler.write("This will print to the terminal")
```

---

## Configuration Guide (config.yaml)

The config file uses YAML format and contains all test parameters for APV and the traffic generator.

### Basic Structure

```yaml
test:
  # APV management interface
  apv_management_ip: 192.168.1.247
  apv_management_port: 22
  apv_username: array
  apv_password: aclab@6768
  apv_enable_password: ""

  traffic_generator:
    # Traffic generator basics
    dperf_path: ~/dperf
    dpdk_path: ~/dpdk
    management_ip: 192.168.1.207
    management_port: 22
    username: root
    password: array

    # Hugepages
    hugepage_frames: 2
    hugepage_size: 1G

    pairs:
      - client:
          # Client config
        server:
          # Server config
        # Shared config
```

### Main Configuration Blocks

#### 1. APV Management Interface

| Parameter | Description | Example |
|------|------|------|
| `apv_management_ip` | APV management IP | 192.168.1.247 |
| `apv_management_port` | SSH port | 22 |
| `apv_username` | Username | array |
| `apv_password` | Password | aclab@6768 |
| `apv_enable_password` | Enable password (optional) | "" |

#### 2. Traffic Generator Basics

| Parameter | Description | Example |
|------|------|------|
| `dperf_path` | DPerf install path | ~/dperf |
| `dpdk_path` | DPDK install path | ~/dpdk |
| `management_ip` | Traffic generator management IP | 192.168.1.207 |
| `management_port` | SSH port | 22 |
| `username` | SSH username | root |
| `password` | SSH password | array |

#### 3. Hugepages

| Parameter | Description | Example |
|------|------|------|
| `hugepage_frames` | Number of hugepages | 2 |
| `hugepage_size` | Hugepage size | 1G (or 2M) |

**Notes**: Hugepages are used by DPDK for high-performance memory management, reducing TLB misses and improving packet processing.

#### 4. Client Configuration (pairs[].client)

| Parameter | Description | Example |
|------|------|------|
| `client_nic_pci` | NIC PCI address (for DPDK binding) | 0000:b6:00.0 |
| `client_nic_name` | NIC interface name | enp182s0f0 |
| `client_nic_driver` | Native NIC driver (for unbind) | i40e |
| `client_ip` | Client starting IP | 10.10.11.1 |
| `source_ip_nums` | Number of simulated source IPs | 60 |
| `client_gw` | Client gateway | 10.10.11.100 |
| `client_duration` | Test duration (s/m/h) | 1s, 570s |
| `client_cpu_core` | Number of CPU cores | 6 |
| `tx_burst` | TX burst size | 1024 |
| `launch_num` | Number of launched sessions | 100 |
| `cc` | Concurrent connections (supports k) | 2k (=2000) |
| `keepalive` | TCP keepalive interval (us/ms/s) | 1us |
| `rss` | Enable RSS | true/false |
| `socket_mem` | DPDK memory pool size (MB) | 1024 |
| `virtual_server_ip` | Target server IP (VIP) | 10.10.11.101 |
| `virtual_server_port` | Target server port | 6667 |
| `server_port_nums` | Number of server ports | 1 |

#### 5. Server Configuration (pairs[].server)

| Parameter | Description | Example |
|------|------|------|
| `server_nic_pci` | NIC PCI address | 0000:b6:00.1 |
| `server_nic_name` | NIC interface name | enp182s0f1 |
| `server_nic_driver` | Native NIC driver | i40e |
| `server_ip` | Server IP | 10.10.12.1 |
| `server_gw` | Server gateway | 10.10.12.100 |
| `server_duration` | Test duration (s/m/h) | 40s, 600s |
| `server_cpu_core` | Number of CPU cores | 14 |
| `tx_burst` | TX burst size | 1024 |
| `keepalive` | TCP keepalive interval | 1us |
| `rss` | Enable RSS | true/false |
| `socket_mem` | DPDK memory pool size (MB) | 1024 |
| `listen_port` | Starting listen port | 6666 |
| `listen_port_nums` | Number of listen ports | 1 |

#### 6. Shared Configuration (pairs[])

| Parameter | Description | Example |
|------|------|------|
| `payload_size` | Payload size (bytes) | 1024 |
| `protocol` | Transport protocol | tcp/udp/http |

### Configuration Recommendations

1. **CPU cores**: Server typically needs more cores than client. Recommend `server_cpu_core` ≥ `client_cpu_core`
2. **Test duration**: Server should run a few seconds longer than client to ensure full traffic reception
3. **Memory**: `socket_mem` should be adjusted based on concurrency and packet size; recommend at least 1024 MB
4. **Concurrency**: `cc` affects resource usage; tune based on targets and system capacity
5. **RSS**: Enable RSS in multi-core environments for better performance

### Multiple Pair Configuration

To test multiple NIC pairs, add multiple blocks under `pairs`:

```yaml
pairs:
  - client:
      client_nic_pci: 0000:b6:00.0
      # ... other settings
    server:
      server_nic_pci: 0000:b6:00.1
      # ... other settings

  - client:
      client_nic_pci: 0000:b7:00.0
      # ... second pair settings
    server:
      server_nic_pci: 0000:b7:00.1
      # ... second pair settings
```

---

## System Requirements

- Python 3.7+
- paramiko (SSH library)
- DPDK and DPerf installed on remote hosts
- Remote hosts must support hugepages and DPDK drivers

## Notes

1. **Privileges**: Some operations (e.g., binding NICs, configuring hugepages) require sudo
2. **Thread safety**: SignalHandler interruption is currently disabled to avoid multi-thread conflicts
3. **Persistent sessions**: Persistent sessions keep state across commands and are suitable for multi-step workflows
4. **Log management**: Each test pair produces its own log file for troubleshooting
5. **Resource cleanup**: Use context managers or ensure `close()` is called to release resources

## License

Please refer to the project's license file.

<!-- FUNCTION_SCAN_BEGIN -->
## Project Function Scan Results

> Scanned **8** Python files, found **18** classes, **4** top-level functions, and **96** methods (total **100** functions)

| File | Classes | Top-level Functions | Methods | Total |
|------|---------|--------------------:|--------:|-----:|
| `APVSetup.py` | 1 | 1 | 10 | 11 |
| `config.py` | 7 | 0 | 3 | 3 |
| `dperfSetup.py` | 1 | 0 | 22 | 22 |
| `main.py` | 0 | 3 | 0 | 3 |
| `output_handler.py` | 1 | 0 | 11 | 11 |
| `ssh_executor.py` | 6 | 0 | 30 | 30 |
| `system_monitor.py` | 1 | 0 | 9 | 9 |
| `trafficGenerator.py` | 1 | 0 | 11 | 11 |

### `APVSetup.py`

**Top-level Functions:**

- `argParser()` (line 216)

**Class `APVSetup`** (line 5):

- `__init__()` (line 6)
- `__del__()` (line 21)
- `_execute_commands()` (line 28)
- `setupUDPLoadBalancer()` (line 37)
- `setupTCPLoadBalancer()` (line 83)
- `setupHTTPLoadBalancer()` (line 133)
- `setupEnv()` (line 168)
- `clearEnv()` (line 189)
- `connect()` (line 210)
- `disconnect()` (line 213)

### `config.py`

**Class `Client`** (line 6):

- _(no methods)_

**Class `ClientConfig`** (line 14):

- _(no methods)_

**Class `ServerConfig`** (line 35):

- _(no methods)_

**Class `TrafficGeneratorPair`** (line 52):

- _(no methods)_

**Class `TrafficGenerator`** (line 61):

- _(no methods)_

**Class `TestConfig`** (line 78):

- _(no methods)_

**Class `Config`** (line 88):

- `__init__()` (line 90)
- `from_yaml()` (line 101)
- `to_dict()` (line 194)

### `dperfSetup.py`

**Class `dperf`** (line 12):

- `__init__()` (line 13)
- `__del__()` (line 64)
- `connect()` (line 71)
- `disconnect()` (line 77)
- `_calc_duration()` (line 87)
- `generateServerConfig()` (line 115)
- `generateClientConfig()` (line 156)
- `runPairTest()` (line 200)
- `outputResults()` (line 232)
- `serverStart()` (line 331)
- `clientStart()` (line 371)
- `parseOutput()` (line 414)
- `bindNICs()` (line 464)
- `unbindNICs()` (line 486)
- `setHugePages()` (line 512)
- `clearHugePages()` (line 534)
- `setupConfig()` (line 546)
- `setupEnv()` (line 567)
- `clearEnv()` (line 581)
- `get_redis_summary()` (line 592)
- `get_redis_test_output()` (line 600)
- `get_redis_monitor_data()` (line 607)

### `main.py`

**Top-level Functions:**

- `parse_arguments()` (line 9)
- `argOverrideConfig()` (line 78)
- `main()` (line 99)

### `output_handler.py`

**Class `OutputHandler`** (line 9):

- `clean_ansi()` (line 13)
- `__init__()` (line 26)
- `write()` (line 51)
- `print_header()` (line 69)
- `print_footer()` (line 74)
- `print_exit_status()` (line 82)
- `print_output()` (line 86)
- `print_error()` (line 92)
- `close()` (line 97)
- `__enter__()` (line 103)
- `__exit__()` (line 107)

### `ssh_executor.py`

**Class `SSHConnectionManager`** (line 13):

- `__init__()` (line 16)
- `connect()` (line 32)
- `close()` (line 48)
- `is_connected()` (line 55)
- `get_client()` (line 59)
- `__enter__()` (line 65)
- `__exit__()` (line 70)

**Class `ScriptReader`** (line 76):

- `read_script()` (line 80)

**Class `SignalHandler`** (line 94):

- `__init__()` (line 97)
- `setup()` (line 101)
- `stop()` (line 122)
- `restore()` (line 126)

**Class `RealTimeStreamReader`** (line 134):

- `__init__()` (line 137)
- `read()` (line 158)
- `_read_remaining()` (line 182)

**Class `CommandExecutor`** (line 189):

- `__init__()` (line 192)
- `execute_simple()` (line 205)
- `execute_realtime()` (line 223)
- `start_session()` (line 242)
- `stop_session()` (line 258)
- `execute_in_session()` (line 267)
- `is_session_active()` (line 308)

**Class `SSHExecutor`** (line 318):

- `__init__()` (line 321)
- `connect()` (line 348)
- `connect_session()` (line 362)
- `execute_script()` (line 366)
- `execute_command()` (line 398)
- `close()` (line 423)
- `__enter__()` (line 431)
- `__exit__()` (line 437)

### `system_monitor.py`

**Class `SystemMonitor`** (line 11):

- `__init__()` (line 17)
- `connect()` (line 67)
- `disconnect()` (line 71)
- `start()` (line 77)
- `stop()` (line 90)
- `_monitor_loop()` (line 100)
- `get_data()` (line 212)
- `get_redis_monitor_data()` (line 220)
- `is_monitoring()` (line 235)

### `trafficGenerator.py`

**Class `TrafficGenerator`** (line 9):

- `__init__()` (line 16)
- `connect()` (line 71)
- `disconnect()` (line 86)
- `setup_env()` (line 101)
- `clearEnv()` (line 122)
- `run_test()` (line 143)
- `_run_sequential()` (line 186)
- `_run_parallel()` (line 205)
- `get_pair()` (line 234)
- `get_monitor()` (line 247)
- `get_pair_count()` (line 255)

<!-- FUNCTION_SCAN_END -->
````