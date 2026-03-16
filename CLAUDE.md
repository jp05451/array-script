# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. 

## output
All outputs must use traditional Chinese

## Running Tests

```bash
# Run unit tests (uses unittest + mocks, no SSH required)
python test_dperf.py

# Run a specific test class
python -m unittest test_dperf.TestDperfParseOutput -v
```

## Running the Test

```bash
# Standard run (uses config.yaml by default)
python main.py -c config.yaml

# Key CLI overrides
python main.py -c config_tcp.yaml -d 1s -p 1024 --sessions 2k
python main.py --dry-run          # Skip actual dperf traffic, test setup/teardown only
python main.py --enable-redis     # Persist monitoring data to Redis
python main.py -o ./results --log ./logs
```

Available protocol configs: `config.yaml`, `config_tcp.yaml`, `config_udp.yaml`, `config_http.yaml`

## Architecture Overview

The system automates DPerf network performance tests against an Array Networks APV load balancer. All remote interaction happens over SSH via `SSHExecutor`.

### Execution Flow (`main.py`)

1. **APVSetup** — SSH into the APV device, clear any existing LB config, then configure TCP/UDP/HTTP load balancers from the YAML config.
2. **TrafficGenerator** — orchestrates all subsequent work:
   - Creates one **SystemMonitor** (monitors the traffic generator host's CPU/RAM and optionally APV CPU) and one **dperf** instance per pair.
   - Calls `setup_env()` → binds NICs to DPDK (`vfio-pci`), sets hugepages, uploads dperf config files.
   - Calls `run_test()` → starts `SystemMonitor`, then runs `dperf.runPairTest()` for each pair (sequentially or in parallel threads).
   - After tests, calls `clearEnv()` → unbinds NICs, clears hugepages.
3. **Results** — each pair writes a CSV to `<output_path>/dperf_pair{i}_results.csv`; `SystemMonitor` writes `<output_path>/system_monitor.csv` in real-time.

### Key Class Relationships

```
Config (from YAML)
  └── TestConfig
        ├── apv_* fields           → APVSetup
        └── TrafficGenerator
              └── pairs[]          → dperf (one per pair)

TrafficGenerator (trafficGenerator.py)
  ├── SystemMonitor                → monitors TG host CPU/RAM + APV CPU
  └── dperf[] (dperfSetup.py)      → manages server/client dperf processes
```

### `SSHExecutor` (ssh_executor.py)

Two modes of SSH execution:
- **Simple**: `execute_command(cmd)` / `execute_script(path)` — opens a fresh channel per call, captures full output.
- **Persistent session**: `connect(persistent_session=True)` → `execute_in_session(cmd, timeout)` — maintains a single interactive shell, preserving working directory and environment across calls. Required for APV CLI (which uses a stateful prompt) and for dperf directory context.

`OutputHandler.clean_ansi()` is used throughout to strip ANSI escape sequences from SSH output before parsing.

### `SystemMonitor` (system_monitor.py)

Accepts a `Config` object and `output_path`; extracts TG and APV connection details from config internally. Two threads:
- **Main thread**: polls `top` (CPU) and `free -m` (RAM) on the TG host every 1 second; appends rows to CSV in real-time.
- **APV thread** (daemon, optional): polls `show statistics cpu` on APV every 3 seconds; stores latest value for the main thread to include in each CSV row.

APV monitoring requires all four APV credential fields to be set in config (`apv_management_ip`, `apv_username`, `apv_password`, `apv_enable_password`). The APV CLI requires entering enable mode at connect time (`enable` → password).

### `dperf` (dperfSetup.py)

Each instance manages one NIC pair. Uses **three separate SSH executors** (management for setup commands, server for dperf server process, client for dperf client process) so server and client can run concurrently in threads. Results are parsed from the `Total Numbers:` block in dperf output and written to CSV via `outputResults()`.

### `Config` (config.py)

Pure dataclass hierarchy loaded from YAML. Key path: `config.test.traffic_generator.pairs[i].client` / `.server`. CLI args in `main.py:argOverrideConfig()` can override `duration`, `cc` (sessions), `payload_size`, and `keepalive` after loading.

### Redis (optional)

`RedisHandler` (RedisDB.py) stores test output and monitor data keyed by pair index and timestamp. Disabled by default (`enable_redis=False`). `SystemMonitor._save_to_redis()` and `dperf.serverStart/clientStart` both call Redis when enabled. `dperf.outputResults()` will prefer Redis data over local if available.

## Output Files

| File | Written by | Content |
|------|-----------|---------|
| `<output_path>/dperf_pair{i}_results.csv` | `dperf.outputResults()` | Per-metric server vs client comparison |
| `<output_path>/system_monitor.csv` | `SystemMonitor` (real-time) | Timestamp, TG CPU%, TG RAM, APV CPU% |
| `<log_path>/dperf_pair{i}*.log` | `SSHExecutor` | Raw SSH session output |
| `<log_path>/system_monitor_tg.log` | `SSHExecutor` | TG monitor SSH session |
| `<log_path>/system_monitor_apv.log` | `SSHExecutor` | APV monitor SSH session |

## Python Version & Dependencies

Requires Python 3.10+ (uses `X | Y` union type syntax). Dependencies: `paramiko`, `pyyaml`, `redis` (optional).
