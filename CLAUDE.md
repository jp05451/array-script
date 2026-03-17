# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## output
All outputs must use traditional Chinese

## Running Tests

```bash
# Run all unit tests (uses unittest + mocks, no SSH required)
python test_dperf.py

# Run a specific test class
python -m unittest test_dperf.TestDperfParseOutput -v

# Other test files (also mock-based, no SSH)
python test_config.py
python test_redisdb.py
```

## Running the Main Script

```bash
# Standard run (uses config.yaml by default)
python main.py -c config.yaml

# Key CLI overrides
python main.py -c config.yaml -d 40s -p 1024 --sessions 2k
python main.py --dry-run          # Skip actual dperf traffic, test setup/teardown only
python main.py --enable-redis     # Persist monitoring data to Redis
python main.py -o ./results --log ./logs
```

Available protocol configs: `config.yaml` (TCP). Additional configs follow the same schema.

## Architecture Overview

The system automates DPerf network performance tests against an Array Networks APV load balancer. All remote interaction happens over SSH via `SSHExecutor`.

### Execution Flow (`main.py`)

1. **APVSetup.clearEnv + setupEnv** — SSH into APV, clear existing LB config, then configure VS/RS/policy for each pair. Naming convention: `{protocol}_vs_{pair_index}` and `{protocol}_rs_{pair_index}` (e.g., `tcp_vs_0`, `tcp_rs_0`).
2. **APVSetup.resolvePortNames** — Runs `show ip address` on APV to populate `pair.apv_client_port` / `pair.apv_server_port` from gateway IPs. These runtime fields start empty in config.
3. **TrafficGenerator.setup_env** — Binds NICs to DPDK (`vfio-pci`), sets hugepages, uploads dperf conf files.
4. **TrafficGenerator.run_test** — Starts `SystemMonitor`, runs `dperf.runPairTest()` per pair (parallel threads), calls `outputSummaryReport()` on completion.
5. **TrafficGenerator.clearEnv** — Unbinds NICs, clears hugepages.
6. **APVSetup.collectSLBStats** — Reconnects APV, runs `show statistics slb all`, handles `--More--` pagination.
7. **APVSetup.parseSLBStats / matchSLBStatsToPairs / outputSLBStats** — Parses VS/RS blocks, matches to pairs by name regex (`_vs_(\d+)$`), writes `apv_slb_stats.csv`.
8. **TrafficGenerator.appendSLBStats** — Appends SLB section to per-pair CSVs and `dperf_summary.csv`.
9. **TrafficGenerator.printFormattedSummary** — Prints vendor-spec formatted console output (global totals + per-pair detail + VS/RS metrics).

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

Two modes:
- **Simple**: `execute_command(cmd)` / `execute_script(path)` — fresh channel per call.
- **Persistent session**: `connect(persistent_session=True)` → `execute_in_session(cmd, timeout)` — single interactive shell, preserves working directory. Required for APV CLI (stateful prompt) and dperf directory context.

The inner `CommandExecutor` is accessible as `ssh_executor._executor`; `execute_in_session` is called directly on it in `APVSetup.collectSLBStats` and `resolvePortNames`.

`OutputHandler.clean_ansi()` strips ANSI escape sequences before parsing throughout.

### `dperf` (dperfSetup.py)

Each instance manages one NIC pair using **three separate SSH executors** (management, server, client) so server and client processes run concurrently in threads.

**Two parsing stages:**
- `parseOutput(log)` — extracts the `Total Numbers:` block at test end → `serverOutput` / `clientOutput` dicts. Used for avg computations.
- `parsePerSecondData(log)` — parses all `seconds X` blocks before `Total Numbers` → `serverPerSecond` / `clientPerSecond` lists. Used for max computations.

**Derived metrics** computed in `_derived()` inside `outputResults()`:
| Metric | Formula |
|--------|---------|
| `avg_throughput_gbps` | `bitsRx / total_seconds / 1e9` |
| `max_throughput_gbps` | `max(per_second bitsRx) / 1e9` |
| `avg_throughput_pps` | `pktRx / total_seconds` |
| `max_throughput_pps` | `max(per_second pktRx)` |
| `avg_cps` | `skOpen / duration_seconds` |
| `max_cps` | `max(per_second skOpen)` |
| `max_cc` | `max(per_second skCon)` ← Total Numbers skCon is always 0 |

`total_seconds` = `duration + server_buffer_time + client_buffer_time`; `duration_seconds` = `duration` only.

### `APVSetup` (APVSetup.py)

SLB VS/RS naming must follow `{protocol}_vs_{pair_index}` / `{protocol}_rs_{pair_index}` for `matchSLBStatsToPairs()` to correctly associate statistics to pairs. The APV CLI requires entering enable mode (`enable` → password) before stat collection.

### `SystemMonitor` (system_monitor.py)

Two threads: main thread polls `top` + `free -m` on TG host every 1s; APV daemon thread polls `show statistics cpu` every 3s. APV monitoring requires all four `apv_*` credential fields in config.

### `Config` (config.py)

Pure dataclass hierarchy. CLI args override `duration`, `cc`, `payload_size`, `keepalive` after loading. `apv_client_port` / `apv_server_port` on `TrafficGeneratorPair` are runtime-only (not in YAML).

### Redis (optional)

`RedisHandler` (RedisDB.py) is disabled by default (`enable_redis=False`). When enabled, `dperf.outputResults()` prefers Redis data over local.

## Output Files

| File | Written by | Content |
|------|-----------|---------|
| `<output>/dperf_pair{i}_results.csv` | `dperf.outputResults()` | Per-metric server vs client + derived metrics; SLB section appended later |
| `<output>/dperf_summary.csv` | `TrafficGenerator.outputSummaryReport()` | Cross-pair summary; SLB section appended later |
| `<output>/apv_slb_stats.csv` | `APVSetup.outputSLBStats()` | VS/RS metrics with Pair/Type columns |
| `<output>/system_monitor.csv` | `SystemMonitor` (real-time) | Timestamp, TG CPU%, TG RAM, APV CPU% |
| `<log>/dperf_pair{i}*.log` | `SSHExecutor` | Raw SSH output |
| `<log>/apv_slb_raw.log` | `APVSetup.collectSLBStats()` | Raw APV stat output for debugging |

## Python Version & Dependencies

Requires Python 3.10+ (uses `X | Y` union type syntax). Dependencies: `paramiko`, `pyyaml`, `redis` (optional).

## Utility Scripts

- `scan_functions.py` — AST-scans all `.py` files and can update README with class/function listings.
- `show_nic_info.py` — SSH helper to display NIC/PCI info on remote TG host.
