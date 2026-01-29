# Array Script - DPerf 測試自動化工具

此專案提供自動化腳本來執行 DPerf 網路效能測試，透過 SSH 連接遠端主機，自動配置 DPDK 環境並運行測試。

## 目錄

- [核心模組說明](#核心模組說明)
  - [1. dperfSetup.py](#1-dperfsetuppy)
  - [2. ssh_executor.py](#2-ssh_executorpy)
  - [3. output_handler.py](#3-output_handlerpy)
  - [4. RedisDB.py](#4-redisdbpy)
  - [5. config.py](#5-configpy)
  - [6. APVSetup.py](#6-apvsetuppy)
  - [7. dperfSetup.py 補充方法](#7-dperfsetuppy-補充方法)
  - [8. scan_functions.py](#8-scan_functionspy)
  - [9. system_monitor.py](#9-system_monitorpy)
  - [10. trafficGenerator.py](#10-trafficgeneratorpy)
- [使用範例](#使用範例)
  - [基本使用](#基本使用)
  - [SSH 命令執行](#ssh-命令執行)
  - [自訂輸出處理](#自訂輸出處理)
- [配置檔案說明 (config.yaml)](#配置檔案說明-configyaml)
  - [基本結構](#基本結構)
  - [主要配置區塊](#主要配置區塊)
  - [配置建議](#配置建議)
  - [多組 Pair 配置](#多組-pair-配置)
- [系統需求](#系統需求)
- [注意事項](#注意事項)
- [專案函式掃描結果](#專案函式掃描結果)

## 核心模組說明

### 1. dperfSetup.py

此模組負責 DPerf 測試的完整設定與執行流程。

#### Class: `dperf`

DPerf 測試的主要控制類別，負責管理整個測試生命週期。

##### 初始化方法
```python
__init__(self, config: Config, pair_index: int = 0, log_path: str = None, output_path: str = None)
```
- **功能**：初始化 DPerf 測試實例
- **參數**：
  - `config`：配置物件，包含所有測試參數
  - `pair_index`：測試對索引，用於識別不同的網路介面對
  - `log_path`：日誌檔案路徑（預設：`./logs/dperf_pair{pair_index}.log`）
  - `output_path`：結果輸出檔案路徑
- **說明**：建立三個 SSH 執行器實例（管理用、server 用、client 用），並初始化測試參數

##### 主要方法

###### `connect()`
- **功能**：建立與遠端主機的 SSH 連接
- **說明**：使用持久化 session 模式連接

###### `disconnect()`
- **功能**：斷開與遠端主機的 SSH 連接

###### `runPairTest()`
- **功能**：執行完整的 DPerf 測試流程
- **返回值**：包含 server 和 client 測試結果的字典
- **說明**：
  1. 設定測試環境（hugepages、綁定 NICs、生成配置檔）
  2. 同時啟動 server 和 client 測試線程
  3. 等待測試完成並收集結果
  4. 將結果輸出到 CSV 檔案

###### `outputResults()`
- **功能**：將測試結果輸出到 CSV 檔案
- **輸出格式**：CSV 格式，包含 Metric、Server、Client 三欄
- **說明**：自動建立輸出目錄（如不存在），將解析後的統計數據寫入檔案

###### `serverStart()`
- **功能**：在獨立線程中啟動 DPerf server 並收集流量數據
- **流程**：
  1. 建立 SSH 連接
  2. 切換到 dperf 目錄
  3. 執行 server 測試腳本
  4. 解析輸出結果
  5. 斷開連接

###### `clientStart()`
- **功能**：在獨立線程中啟動 DPerf client 並收集流量數據
- **流程**：與 `serverStart()` 相似，但執行 client 端測試

###### `parseOutput(log)`
- **功能**：解析 DPerf 測試輸出日誌
- **參數**：`log` - 測試輸出的日誌字串
- **返回值**：包含各項統計指標的字典
- **說明**：
  - 移除 ANSI 轉義序列（顏色代碼）
  - 尋找 "Total Numbers" 區塊
  - 將統計數據解析為字典格式（key-value pairs）

###### `bindNICs()`
- **功能**：將網路介面卡綁定到 DPDK 驅動程式
- **說明**：
  1. 停用網路連接
  2. 使用 dpdk-devbind.py 將 NIC 綁定到 vfio-pci 驅動
  3. 使用 no-iommu 模式

###### `unbindNICs()`
- **功能**：解綁 NIC 並恢復原生驅動程式
- **說明**：
  1. 將 NIC 綁定回原生驅動
  2. 重新啟動網路連接
  3. 顯示當前綁定狀態

###### `setHugePages()`
- **功能**：配置系統 hugepages
- **說明**：根據配置檔中的參數設定 hugepage 大小和數量

###### `setupConfig()`
- **功能**：生成並上傳 DPerf 配置檔案
- **說明**：
  - 建立 config 目錄（如不存在）
  - 生成 server 和 client 配置檔
  - 上傳到遠端主機

###### `setupEnv()`
- **功能**：設定完整的 DPerf 測試環境
- **流程**：
  1. 建立 SSH 連接
  2. 設定 hugepages
  3. 綁定 NICs
  4. 建立配置檔案
  5. 斷開連接

###### `generateServerConfig()`
- **功能**：生成 DPerf server 配置檔內容
- **返回值**：配置檔字串
- **配置項目**：mode、tx_burst、cpu、rss、socket_mem、protocol、duration、payload_size、keepalive、port、client、server、listen 等

###### `generateClientConfig()`
- **功能**：生成 DPerf client 配置檔內容
- **返回值**：配置檔字串
- **配置項目**：mode、tx_burst、launch_num、cpu、rss、socket_mem、protocol、payload_size、duration、cc、keepalive、port、client、server、listen 等

---

### 2. ssh_executor.py

此模組提供 SSH 連接管理和遠端命令執行功能。

#### Class: `SSHConnectionManager`

SSH 連接管理器，負責建立和維護 SSH 連接。

##### 初始化方法
```python
__init__(self, host: str, port: int, user: str, password: str)
```
- **功能**：初始化 SSH 連接管理器
- **參數**：
  - `host`：主機地址
  - `port`：SSH 端口號
  - `user`：登入用戶名
  - `password`：登入密碼

##### 主要方法

###### `connect()`
- **功能**：建立 SSH 連接
- **說明**：使用 paramiko 建立 SSH 連接，自動接受主機金鑰

###### `close()`
- **功能**：關閉 SSH 連接

###### `is_connected()`
- **功能**：檢查是否已連接
- **返回值**：布林值

###### `get_client()`
- **功能**：獲取 SSH 客戶端實例
- **返回值**：paramiko.SSHClient 物件

###### `__enter__()` / `__exit__()`
- **功能**：支持 with 語句的上下文管理

---

#### Class: `ScriptReader`

腳本讀取器，用於讀取本地腳本檔案。

##### 靜態方法

###### `read_script(script_path: str)`
- **功能**：讀取腳本檔案內容
- **參數**：`script_path` - 腳本檔案路徑
- **返回值**：腳本內容字串

---

#### Class: `SignalHandler`

信號處理器，用於處理中斷信號（目前暫時關閉以避免多線程衝突）。

##### 方法

###### `setup(stdin)`
- **功能**：設置信號處理器
- **參數**：`stdin` - SSH 標準輸入流
- **說明**：目前為空實作，預留給未來使用

###### `stop()`
- **功能**：標記為已中斷

###### `restore()`
- **功能**：恢復原始信號處理器

---

#### Class: `RealTimeStreamReader`

實時流讀取器，用於即時讀取和顯示命令輸出。

##### 初始化方法
```python
__init__(self, stdout, stderr, signal_handler: SignalHandler, output_handler: OutputHandler)
```
- **參數**：
  - `stdout`：標準輸出流
  - `stderr`：標準錯誤流
  - `signal_handler`：信號處理器實例
  - `output_handler`：輸出處理器實例

##### 主要方法

###### `read()`
- **功能**：讀取並即時打印命令輸出
- **說明**：
  - 持續讀取輸出直到命令完成
  - 支持中斷信號處理
  - 分別處理標準輸出和錯誤輸出

###### `_read_remaining()`
- **功能**：讀取剩餘的輸出內容（私有方法）

---

#### Class: `CommandExecutor`

命令執行器，負責在遠端主機上執行命令。

##### 初始化方法
```python
__init__(self, ssh_client: paramiko.SSHClient, output_handler: OutputHandler)
```
- **參數**：
  - `ssh_client`：SSH 客戶端實例
  - `output_handler`：輸出處理器實例

##### 主要方法

###### `execute_simple(command: str)`
- **功能**：執行簡單命令並等待完成
- **參數**：`command` - 要執行的命令
- **返回值**：`(output, error, exit_status)` 元組

###### `execute_realtime(command: str)`
- **功能**：執行命令並即時輸出結果
- **參數**：`command` - 要執行的命令

###### `start_session()`
- **功能**：啟動持久的互動式 shell session
- **說明**：允許在多個命令之間保持狀態（目錄、環境變數等）

###### `stop_session()`
- **功能**：停止持久的 shell session

###### `execute_in_session(command: str, timeout: float = 10.0)`
- **功能**：在持久 session 中執行命令
- **參數**：
  - `command`：要執行的命令
  - `timeout`：等待輸出的超時時間（秒）
- **返回值**：命令的輸出字串

###### `is_session_active()`
- **功能**：檢查 session 是否活躍
- **返回值**：布林值

---

#### Class: `SSHExecutor`

SSH 執行器（高層封裝），整合所有 SSH 相關功能的主要介面。

##### 初始化方法
```python
__init__(self, host: str, port: int, user: str, password: str, log_path: Optional[str] = None)
```
- **參數**：
  - `host`：主機地址
  - `port`：SSH 端口號
  - `user`：登入用戶名
  - `password`：登入密碼
  - `log_path`：日誌輸出檔案路徑（若為 None 則輸出到 stdout）

##### 主要方法

###### `connect(persistent_session: bool = False)`
- **功能**：建立 SSH 連接
- **參數**：`persistent_session` - 是否啟用持久 session 模式
- **說明**：持久 session 可在多個命令間保持狀態

###### `connect_session()`
- **功能**：建立持久 SSH 連接（快捷方法）
- **說明**：等同於 `connect(persistent_session=True)`

###### `execute_script(script_path: str, real_time: bool = False)`
- **功能**：執行本地 shell 腳本檔案
- **參數**：
  - `script_path`：腳本檔案路徑
  - `real_time`：是否即時輸出
- **返回值**：
  - 若 `real_time=False`：返回 `(output, error, exit_status)`
  - 若 `real_time=True`：返回 None

###### `execute_command(command: str, real_time: bool = False)`
- **功能**：執行單一命令
- **參數**：
  - `command`：要執行的命令
  - `real_time`：是否即時輸出
- **返回值**：
  - 若 `real_time=False`：返回 `(output, error, exit_status)`
  - 若 `real_time=True`：返回 None
- **說明**：若啟用 persistent_session，則在持久 session 中執行

###### `close()`
- **功能**：關閉 SSH 連接並清理資源
- **說明**：停止 session（如果活躍）、關閉連接、關閉輸出處理器

###### `__enter__()` / `__exit__()`
- **功能**：支持 with 語句的上下文管理

---

### 3. output_handler.py

此模組提供輸出處理功能，支援輸出到 stdout 或檔案。

#### Class: `OutputHandler`

輸出處理器，統一管理所有輸出操作。

##### 初始化方法
```python
__init__(self, output_path: Optional[str] = None)
```
- **功能**：初始化輸出處理器
- **參數**：`output_path` - 輸出檔案路徑（若為 None 則輸出到 stdout）
- **說明**：
  - 自動建立輸出目錄（如不存在）
  - 開啟檔案準備寫入
  - 若開啟檔案失敗，自動降級為 stdout 輸出

##### 靜態方法

###### `clean_ansi(text: str)` (staticmethod)
- **功能**：移除 ANSI 轉義序列和終端控制字符
- **參數**：`text` - 包含 ANSI 控制字符的文本
- **返回值**：清理後的純文本
- **說明**：移除顏色代碼、游標控制等 ANSI 轉義序列

##### 主要方法

###### `write(message: str, end: str = '\n', flush: bool = False)`
- **功能**：寫入訊息到輸出目標
- **參數**：
  - `message`：要輸出的訊息
  - `end`：結尾字符（預設為換行）
  - `flush`：是否立即刷新緩衝區
- **說明**：自動移除 ANSI 轉義序列（顏色代碼）

###### `print_header(script_path: str)`
- **功能**：打印執行頭部資訊
- **參數**：`script_path` - 正在執行的腳本路徑
- **輸出格式**：
  ```
  開始執行 {script_path} 中的指令...
  --------------------------------------------------
  ```

###### `print_footer(interrupted: bool = False)`
- **功能**：打印執行尾部資訊
- **參數**：`interrupted` - 是否被使用者中斷
- **輸出格式**：
  ```
  --------------------------------------------------
  執行完成 / 程式已被使用者中斷
  ```

###### `print_exit_status(exit_status: int)`
- **功能**：打印命令退出狀態碼
- **參數**：`exit_status` - 退出狀態碼

###### `print_output(output: str, prefix: str = "執行結果")`
- **功能**：打印標準輸出
- **參數**：
  - `output`：輸出內容
  - `prefix`：輸出前綴標籤

###### `print_error(error: str)`
- **功能**：打印錯誤輸出
- **參數**：`error` - 錯誤訊息內容

###### `close()`
- **功能**：關閉輸出檔案
- **說明**：若有開啟檔案，則關閉檔案句柄

###### `__enter__()` / `__exit__()`
- **功能**：支持 with 語句的上下文管理
- **說明**：確保檔案資源正確釋放

---

### 4. RedisDB.py

此模組提供 Redis 資料庫處理功能，用於儲存和檢索測試監控數據。

#### Class: `RedisHandler`

Redis 資料庫處理器，負責管理測試數據的持久化儲存。

##### 初始化方法
```python
__init__(self, host: str = "localhost", port: int = 6379, db: int = 0, password: Optional[str] = None, decode_responses: bool = True)
```
- **功能**：初始化 Redis 連接
- **參數**：
  - `host`：Redis 主機地址（預設：localhost）
  - `port`：Redis 端口號（預設：6379）
  - `db`：Redis 數據庫編號（預設：0）
  - `password`：Redis 密碼（可選）
  - `decode_responses`：是否自動解碼響應為字符串（預設：True）
- **說明**：自動測試連接並輸出連接狀態

##### 主要方法

###### `is_connected()`
- **功能**：檢查是否成功連接到 Redis
- **返回值**：布林值，True 表示已連接

###### `save_monitor_data(pair_index: int, timestamp: str, cpu_usage: float, ram_used: int, ram_total: int, ram_usage: float)`
- **功能**：儲存監控數據到 Redis
- **參數**：
  - `pair_index`：pair 索引
  - `timestamp`：時間戳（格式：'%Y-%m-%d %H:%M:%S'）
  - `cpu_usage`：CPU 使用率百分比
  - `ram_used`：已使用 RAM (MB)
  - `ram_total`：總 RAM (MB)
  - `ram_usage`：RAM 使用率百分比
- **返回值**：成功返回 True，否則返回 False
- **資料結構**：
  - Key：`monitor:pair{index}:{timestamp}`
  - 使用 Sorted Set 按時間排序：`monitor:pair{index}:timeline`

###### `save_test_output(pair_index: int, role: str, output: Dict, timestamp: Optional[str] = None)`
- **功能**：儲存測試輸出數據（server 或 client）
- **參數**：
  - `pair_index`：pair 索引
  - `role`：角色（'server' 或 'client'）
  - `output`：測試輸出數據字典
  - `timestamp`：時間戳（可選，預設使用當前時間）
- **返回值**：成功返回 True，否則返回 False
- **資料結構**：
  - Info Key：`test:pair{index}:{role}:{timestamp}:info`
  - Metrics Key：`test:pair{index}:{role}:{timestamp}:metrics`

###### `get_monitor_data(pair_index: int, start_time: Optional[str] = None, end_time: Optional[str] = None)`
- **功能**：獲取監控數據
- **參數**：
  - `pair_index`：pair 索引
  - `start_time`：起始時間（可選）
  - `end_time`：結束時間（可選）
- **返回值**：監控數據列表（List[Dict]）

###### `get_test_output(pair_index: int, role: str, timestamp: Optional[str] = None, include_metrics: bool = True)`
- **功能**：獲取測試輸出數據
- **參數**：
  - `pair_index`：pair 索引
  - `role`：角色（'server' 或 'client'）
  - `timestamp`：時間戳（可選，若不提供則返回最新的）
  - `include_metrics`：是否包含 metrics 數據（預設 True）
- **返回值**：測試輸出數據字典，包含 'info' 和 'metrics'

###### `clear_pair_data(pair_index: int)`
- **功能**：清除指定 pair 的所有數據
- **參數**：`pair_index` - pair 索引
- **返回值**：成功返回 True，否則返回 False
- **說明**：刪除該 pair 的所有監控數據和測試輸出

###### `get_all_test_outputs(pair_index: int, role: str, start_time: Optional[str] = None, end_time: Optional[str] = None, include_metrics: bool = True)`
- **功能**：獲取指定時間範圍內的所有測試輸出數據
- **參數**：
  - `pair_index`：pair 索引
  - `role`：角色（'server' 或 'client'）
  - `start_time`：起始時間（可選）
  - `end_time`：結束時間（可選）
  - `include_metrics`：是否包含 metrics 數據
- **返回值**：測試輸出數據列表（List[Dict]）

###### `get_specific_metrics(pair_index: int, role: str, metric_names: List[str], timestamp: Optional[str] = None)`
- **功能**：獲取特定的 metrics 數據
- **參數**：
  - `pair_index`：pair 索引
  - `role`：角色（'server' 或 'client'）
  - `metric_names`：要查詢的 metric 名稱列表（例如 ['duration', 'ackDup']）
  - `timestamp`：時間戳（可選，若不提供則返回最新的）
- **返回值**：包含指定 metrics 的字典

###### `get_pair_summary(pair_index: int)`
- **功能**：獲取指定 pair 的數據摘要
- **參數**：`pair_index` - pair 索引
- **返回值**：摘要字典，包含：
  - `pair_index`：pair 索引
  - `monitor_count`：監控數據筆數
  - `server_output_count`：Server 輸出筆數
  - `client_output_count`：Client 輸出筆數

###### `close()`
- **功能**：關閉 Redis 連接
- **說明**：釋放連接資源

---

### 5. config.py

此模組提供配置管理功能，使用 dataclass 定義結構化配置。

#### Dataclasses

##### `Client`
- **功能**：客戶端基本配置
- **欄位**：
  - `nic_pci: str`：網卡 PCI 位址
  - `ip: str`：IP 位址
  - `gw: str`：閘道位址

##### `ClientConfig`
- **功能**：客戶端詳細配置
- **欄位**：
  | 欄位 | 類型 | 預設值 | 說明 |
  |------|------|--------|------|
  | `client_nic_pci` | str | "" | 網卡 PCI 位址 |
  | `client_nic_name` | str | "" | 網卡介面名稱 |
  | `client_nic_driver` | str | "i40e" | 網卡驅動程式 |
  | `client_ip` | str | "" | 客戶端 IP |
  | `source_ip_nums` | int | 0 | 模擬源 IP 數量 |
  | `client_gw` | str | "" | 客戶端閘道 |
  | `client_duration` | str | "" | 測試持續時間 |
  | `client_cpu_core` | int | 0 | CPU 核心數 |
  | `tx_burst` | int | 0 | 傳送批次大小 |
  | `launch_num` | int | 0 | 啟動連線數 |
  | `cc` | str | "" | 併發連線數 |
  | `keepalive` | str | "" | keepalive 間隔 |
  | `rss` | bool | False | 是否啟用 RSS |
  | `socket_mem` | int | 0 | 記憶體池大小 |
  | `virtual_server_ip` | str | "" | 目標伺服器 IP |
  | `virtual_server_port` | int | 0 | 目標伺服器埠 |
  | `virtual_server_port_nums` | int | 1 | 伺服器埠數量 |

##### `ServerConfig`
- **功能**：伺服器詳細配置
- **欄位**：
  | 欄位 | 類型 | 預設值 | 說明 |
  |------|------|--------|------|
  | `server_nic_pci` | str | "" | 網卡 PCI 位址 |
  | `server_nic_name` | str | "" | 網卡介面名稱 |
  | `server_nic_driver` | str | "i40e" | 網卡驅動程式 |
  | `server_ip` | str | "" | 伺服器 IP |
  | `server_gw` | str | "" | 伺服器閘道 |
  | `server_duration` | str | "" | 測試持續時間 |
  | `server_cpu_core` | int | 0 | CPU 核心數 |
  | `tx_burst` | int | 0 | 傳送批次大小 |
  | `keepalive` | str | "" | keepalive 間隔 |
  | `rss` | bool | False | 是否啟用 RSS |
  | `socket_mem` | int | 0 | 記憶體池大小 |
  | `listen_port` | int | 0 | 監聽埠號 |
  | `listen_port_nums` | int | 1 | 監聽埠數量 |

##### `TrafficGeneratorPair`
- **功能**：流量產生器配對配置
- **欄位**：
  - `client: ClientConfig`：客戶端配置
  - `server: ServerConfig`：伺服器配置
  - `payload_size: int`：封包有效負載大小（預設：0）
  - `protocol: str`：傳輸協定（預設："tcp"）

##### `TrafficGenerator`
- **功能**：流量產生器配置
- **欄位**：
  - `management_ip: str`：管理介面 IP
  - `management_port: int`：管理介面埠號
  - `username: str`：SSH 用戶名
  - `password: str`：SSH 密碼
  - `dpdk_path: str`：DPDK 安裝路徑
  - `dperf_path: str`：DPerf 安裝路徑
  - `hugepage_frames: int`：Hugepage 數量（預設：2）
  - `hugepage_size: str`：Hugepage 大小（預設："1G"）
  - `pairs: List[TrafficGeneratorPair]`：測試配對列表

##### `TestConfig`
- **功能**：測試配置
- **欄位**：
  - `apv_management_ip: str`：APV 管理 IP
  - `apv_management_port: int`：APV 管理埠號
  - `apv_username: str`：APV 用戶名
  - `apv_password: str`：APV 密碼
  - `apv_enable_password: str`：APV enable 密碼
  - `traffic_generator: TrafficGenerator`：流量產生器配置

#### Class: `Config`

主配置類別，負責載入和管理所有配置。

##### 初始化方法
```python
__init__(self, yaml_path: str = None)
```
- **功能**：初始化配置
- **參數**：`yaml_path` - YAML 配置檔案路徑（可選，若提供則自動載入）

##### 主要方法

###### `from_yaml(yaml_path: str)`
- **功能**：從 YAML 檔案載入配置
- **參數**：`yaml_path` - YAML 配置檔案路徑
- **返回值**：self（支持鏈式調用）
- **說明**：解析 YAML 並建立對應的 dataclass 物件

###### `to_dict()`
- **功能**：將配置轉換為字典
- **返回值**：配置字典（Dict[str, Any]）
- **說明**：將所有 dataclass 結構轉換為可序列化的字典格式

---

### 6. APVSetup.py

此模組負責 APV 負載均衡器的設定與管理。

#### Class: `APVSetup`

APV 負載均衡器設置類別，負責配置各種協定的負載均衡規則。

##### 初始化方法
```python
__init__(self, config: Config, log_path: str = 'logs')
```
- **功能**：初始化 APV 設置
- **參數**：
  - `config`：配置物件
  - `log_path`：日誌檔案路徑（預設：'logs'）
- **說明**：從配置中提取 APV 連接資訊，建立 SSH 執行器

##### 主要方法

###### `connect()`
- **功能**：建立與 APV 設備的 SSH 連接
- **說明**：使用持久 session 模式連接

###### `disconnect()`
- **功能**：斷開與 APV 設備的連接

###### `_execute_commands(commands: list, dry_run: bool = False)`
- **功能**：執行指令陣列（私有方法）
- **參數**：
  - `commands`：要執行的指令列表
  - `dry_run`：若為 True，僅列印指令不執行
- **說明**：根據 dry_run 模式決定是列印還是實際執行指令

###### `setupUDPLoadBalancer(pair_index: int, dry_run: bool = False, clear: bool = False)`
- **功能**：設置 UDP 負載均衡器
- **參數**：
  - `pair_index`：pair 索引
  - `dry_run`：是否為模擬執行模式
  - `clear`：是否清除現有設定
- **設定項目**：
  - Real Server 配置
  - Virtual Server 配置
  - 負載均衡群組（使用 Round-Robin）
  - 策略綁定

###### `setupTCPLoadBalancer(pair_index: int, dry_run: bool = False, clear: bool = False)`
- **功能**：設置 TCP 負載均衡器
- **參數**：同 `setupUDPLoadBalancer`
- **說明**：配置邏輯與 UDP 相似，但使用 TCP 協定

###### `setupHTTPLoadBalancer(pair_index: int, dry_run: bool = False, clear: bool = False)`
- **功能**：設置 HTTP 負載均衡器
- **參數**：同 `setupUDPLoadBalancer`
- **說明**：配置邏輯與 TCP 相似，但使用 HTTP 協定

###### `setupEnv(dry_run: bool = False, clear: bool = False)`
- **功能**：設定 APV 環境
- **參數**：
  - `dry_run`：是否為模擬執行模式
  - `clear`：是否清除現有設定
- **流程**：
  1. 進入 enable 模式
  2. 輸入 enable 密碼
  3. 進入 config terminal
  4. 根據每個 pair 的協定設置對應的負載均衡器
  5. 儲存配置（write memory）

#### 獨立函數

###### `argParser()`
- **功能**：命令列參數解析
- **返回值**：解析後的參數物件
- **支援參數**：
  - `--dry-run`：模擬執行模式
  - `--clear`：清除負載均衡設定
  - `-c, --config`：配置檔案路徑

---

### 7. dperfSetup.py 補充方法

以下是 `dperf` class 的額外方法（補充原有文檔）：

##### Redis 整合方法

###### `monitorStart()`
- **功能**：開始監控 CPU 和 RAM 使用率
- **說明**：
  - 每秒記錄一次系統資源使用情況
  - 同時寫入本地 CSV 檔案和 Redis（如果啟用）
  - 在獨立線程中運行

###### `monitorStop()`
- **功能**：停止監控
- **說明**：設置 monitoring 標誌為 False，使監控循環結束

###### `get_redis_summary()`
- **功能**：獲取 Redis 中該 pair 的數據摘要
- **返回值**：摘要字典或 None（若 Redis 未連接）

###### `get_redis_monitor_data(start_time=None, end_time=None)`
- **功能**：從 Redis 獲取監控數據
- **參數**：
  - `start_time`：起始時間（可選）
  - `end_time`：結束時間（可選）
- **返回值**：監控數據列表

###### `get_redis_test_output(role: str)`
- **功能**：從 Redis 獲取測試輸出數據
- **參數**：`role` - 角色（'server' 或 'client'）
- **返回值**：測試輸出數據字典或 None

##### 初始化方法更新
```python
__init__(self, config: Config, pair_index: int = 0, log_path: str = None, output_path: str = None, redis_host: str = "localhost", redis_port: int = 6379, redis_db: int = 0, enable_redis: bool = True)
```
- **新增參數**：
  - `redis_host`：Redis 主機地址（預設：localhost）
  - `redis_port`：Redis 端口（預設：6379）
  - `redis_db`：Redis 數據庫編號（預設：0）
  - `enable_redis`：是否啟用 Redis 儲存（預設：True）

---

### 9. system_monitor.py

此模組提供遠端主機系統資源監控功能，用於在測試期間追蹤 CPU 和 RAM 使用率。

#### Class: `SystemMonitor`

系統監控類別，用於監控遠端主機的 CPU 和 RAM 使用率。一台機器只需要一個 monitor 實例，可以被多個 pair 共享使用。

##### 初始化方法
```python
__init__(self, management_ip: str, management_port: int, username: str, password: str, log_path: str = "./logs", redis_host: str = "localhost", redis_port: int = 6379, redis_db: int = 0, enable_redis: bool = True)
```
- **功能**：初始化系統監控器
- **參數**：
  - `management_ip`：遠端主機 IP 位址
  - `management_port`：SSH 端口號
  - `username`：SSH 登入用戶名
  - `password`：SSH 登入密碼
  - `log_path`：日誌輸出路徑（預設：`./logs`）
  - `redis_host`：Redis 主機地址（預設：localhost）
  - `redis_port`：Redis 端口號（預設：6379）
  - `redis_db`：Redis 數據庫編號（預設：0）
  - `enable_redis`：是否啟用 Redis 儲存（預設：True）

##### 主要方法

###### `connect()`
- **功能**：建立與遠端主機的 SSH 連接

###### `disconnect()`
- **功能**：斷開與遠端主機的 SSH 連接

###### `start(output_file: str = None)`
- **功能**：在新線程中啟動監控
- **參數**：`output_file` - 監控數據輸出檔案路徑（若為 None 則使用預設路徑）
- **說明**：啟動獨立線程持續記錄 CPU 和 RAM 使用率

###### `stop()`
- **功能**：停止監控
- **說明**：設置停止標誌並等待監控線程結束

###### `_monitor_loop(output_file: str = None)`
- **功能**：監控迴圈（私有方法）
- **參數**：`output_file` - 監控數據輸出檔案路徑
- **說明**：每秒記錄一次 CPU 和 RAM 使用率，同時寫入本地 CSV 檔案和 Redis（如果啟用）

###### `get_data()`
- **功能**：獲取監控數據
- **返回值**：監控數據列表（list）

###### `get_redis_monitor_data(start_time=None, end_time=None)`
- **功能**：從 Redis 獲取監控數據
- **參數**：
  - `start_time`：起始時間（可選）
  - `end_time`：結束時間（可選）
- **返回值**：監控數據列表（list）

###### `is_monitoring()`
- **功能**：檢查監控是否正在進行中
- **返回值**：布林值，True 表示監控中

---

### 10. trafficGenerator.py

此模組提供流量產生器的統一管理介面，封裝多組 dperf pair 和共用的 SystemMonitor。

#### Class: `TrafficGenerator`

流量產生器管理類別，封裝多組 dperf pair 和一個共用的 SystemMonitor，提供統一的介面來管理流量測試。

##### 初始化方法
```python
__init__(self, config: Config, log_path: str = "./logs", output_path: str = "./results", redis_host: str = "localhost", redis_port: int = 6379, redis_db: int = 0, enable_redis: bool = True)
```
- **功能**：初始化流量產生器，建立多組 dperf pair 和 SystemMonitor
- **參數**：
  - `config`：配置物件，包含所有測試參數
  - `log_path`：日誌輸出路徑（預設：`./logs`）
  - `output_path`：結果輸出路徑（預設：`./results`）
  - `redis_host`：Redis 主機地址（預設：localhost）
  - `redis_port`：Redis 端口號（預設：6379）
  - `redis_db`：Redis 數據庫編號（預設：0）
  - `enable_redis`：是否啟用 Redis 儲存（預設：True）

##### 主要方法

###### `connect()`
- **功能**：建立與遠端主機的連接
- **說明**：同時連接 SystemMonitor 和所有 dperf pair

###### `disconnect()`
- **功能**：斷開所有連接
- **說明**：斷開所有 dperf pair 和 SystemMonitor 的連接

###### `setup_env(pair_indices: list = None)`
- **功能**：設定測試環境
- **參數**：`pair_indices` - 要設定的 pair 索引列表（若為 None 則設定所有 pair）
- **說明**：依序對指定的 pair 設定 DPDK 環境（hugepages、綁定 NIC、生成配置檔）

###### `run_test(pair_indices: list = None, enable_monitor: bool = True, parallel: bool = False, monitor_output_file: str = None)`
- **功能**：執行流量測試
- **參數**：
  - `pair_indices`：要測試的 pair 索引列表（若為 None 則測試所有 pair）
  - `enable_monitor`：是否啟用系統監控（預設：True）
  - `parallel`：是否平行執行多組 pair 測試（預設：False）
  - `monitor_output_file`：監控數據輸出檔案路徑
- **返回值**：測試結果字典，包含各 pair 的 server/client 輸出和監控數據
- **說明**：根據 parallel 參數決定使用循序或平行模式執行測試

###### `_run_sequential(pair_indices: list)`
- **功能**：循序執行測試（私有方法）
- **參數**：`pair_indices` - 要測試的 pair 索引列表
- **返回值**：測試結果字典

###### `_run_parallel(pair_indices: list)`
- **功能**：平行執行測試（私有方法）
- **參數**：`pair_indices` - 要測試的 pair 索引列表
- **返回值**：測試結果字典
- **說明**：使用多線程同時執行多組 pair 測試

###### `get_pair(pair_index: int)`
- **功能**：取得指定的 dperf pair 實例
- **參數**：`pair_index` - pair 索引
- **返回值**：`dperf` 實例，若索引無效則返回 None

###### `get_monitor()`
- **功能**：取得 SystemMonitor 實例
- **返回值**：`SystemMonitor` 實例

###### `get_pair_count()`
- **功能**：取得 pair 數量
- **返回值**：整數，pair 的總數

---

## 使用範例

### 基本使用
```python
from config import Config
from dperfSetup import dperf

# 載入配置
config = Config()
config_data = config.from_yaml("config.yaml")

# 建立測試實例
test = dperf(config=config_data, pair_index=0)

# 設定測試環境
test.setupEnv()

# 執行測試
output = test.runPairTest()
print(output)
```

### SSH 命令執行
```python
from ssh_executor import SSHExecutor

# 建立 SSH 執行器
executor = SSHExecutor(
    host="192.168.1.100",
    port=22,
    user="admin",
    password="password",
    log_path="./logs/test.log"
)

# 使用持久 session
executor.connect(persistent_session=True)
executor.execute_command("cd /home/user")
executor.execute_command("ls -la")
executor.close()
```

### 自訂輸出處理
```python
from output_handler import OutputHandler

# 輸出到檔案
with OutputHandler(output_path="./output.txt") as handler:
    handler.write("測試開始")
    handler.print_header("test_script.sh")
    handler.write("測試中...")
    handler.print_footer()

# 輸出到 stdout
handler = OutputHandler()
handler.write("這會輸出到終端")
```

---

## 配置檔案說明 (config.yaml)

配置檔案使用 YAML 格式，包含 APV 設備和流量產生器的所有測試參數。

### 基本結構

```yaml
test:
  # APV 管理介面配置
  apv_management_ip: 192.168.1.247
  apv_management_port: 22
  apv_username: array
  apv_password: aclab@6768
  apv_enable_password: ""

  traffic_generator:
    # 流量產生器基本設定
    dperf_path: ~/dperf
    dpdk_path: ~/dpdk
    management_ip: 192.168.1.207
    management_port: 22
    username: root
    password: array

    # Hugepages 配置
    hugepage_frames: 2
    hugepage_size: 1G

    pairs:
      - client:
          # Client 端配置
        server:
          # Server 端配置
        # 共用配置
```

### 主要配置區塊

#### 1. APV 管理介面配置

| 參數 | 說明 | 範例 |
|------|------|------|
| `apv_management_ip` | APV 設備管理介面 IP 位址 | 192.168.1.247 |
| `apv_management_port` | SSH 連接埠號 | 22 |
| `apv_username` | 登入使用者名稱 | array |
| `apv_password` | 登入密碼 | aclab@6768 |
| `apv_enable_password` | Enable 模式密碼（若不需要可留空） | "" |

#### 2. 流量產生器基本設定

| 參數 | 說明 | 範例 |
|------|------|------|
| `dperf_path` | DPerf 安裝路徑 | ~/dperf |
| `dpdk_path` | DPDK 安裝路徑 | ~/dpdk |
| `management_ip` | 流量產生器管理介面 IP | 192.168.1.207 |
| `management_port` | SSH 連接埠號 | 22 |
| `username` | SSH 登入使用者名稱 | root |
| `password` | SSH 登入密碼 | array |

#### 3. Hugepages 配置

| 參數 | 說明 | 範例 |
|------|------|------|
| `hugepage_frames` | Hugepage 分配數量 | 2 |
| `hugepage_size` | 每個 Hugepage 的大小 | 1G (或 2M) |

**說明**：Hugepages 用於 DPDK 的高效能記憶體管理，減少 TLB miss 並提升封包處理效能。

#### 4. Client 端配置 (pairs[].client)

| 參數 | 說明 | 範例 |
|------|------|------|
| `client_nic_pci` | 網卡 PCI 位址，用於 DPDK 綁定 | 0000:b6:00.0 |
| `client_nic_name` | 網卡介面名稱 | enp182s0f0 |
| `client_nic_driver` | 網卡原生驅動程式，解綁時恢復用 | i40e |
| `client_ip` | 客戶端起始 IP 位址 | 10.10.11.1 |
| `source_ip_nums` | 模擬的源 IP 數量 | 60 |
| `client_gw` | 客戶端預設閘道 | 10.10.11.100 |
| `client_duration` | 測試持續時間 (s/m/h) | 1s, 570s |
| `client_cpu_core` | 使用的 CPU 核心數量 | 6 |
| `tx_burst` | 每次傳送的封包批次大小 | 1024 |
| `launch_num` | 同時啟動的連線數量 | 100 |
| `cc` | 併發連線數 (支援 k 單位) | 2k (=2000) |
| `keepalive` | TCP keepalive 間隔 (us/ms/s) | 1us |
| `rss` | 啟用 RSS 多佇列負載均衡 | true/false |
| `socket_mem` | DPDK 記憶體池大小 (MB) | 1024 |
| `virtual_server_ip` | 目標伺服器 IP (可能為 VIP) | 10.10.11.101 |
| `virtual_server_port` | 目標伺服器連接埠 | 6667 |
| `server_port_nums` | 伺服器埠數量 | 1 |

#### 5. Server 端配置 (pairs[].server)

| 參數 | 說明 | 範例 |
|------|------|------|
| `server_nic_pci` | 網卡 PCI 位址 | 0000:b6:00.1 |
| `server_nic_name` | 網卡介面名稱 | enp182s0f1 |
| `server_nic_driver` | 網卡原生驅動程式 | i40e |
| `server_ip` | 伺服器 IP 位址 | 10.10.12.1 |
| `server_gw` | 伺服器預設閘道 | 10.10.12.100 |
| `server_duration` | 測試持續時間 (s/m/h) | 40s, 600s |
| `server_cpu_core` | 使用的 CPU 核心數量 | 14 |
| `tx_burst` | 每次傳送的封包批次大小 | 1024 |
| `keepalive` | TCP keepalive 間隔 | 1us |
| `rss` | 啟用 RSS | true/false |
| `socket_mem` | DPDK 記憶體池大小 (MB) | 1024 |
| `listen_port` | 監聽的起始埠號 | 6666 |
| `listen_port_nums` | 監聽的埠數量 | 1 |

#### 6. 共用配置 (pairs[])

| 參數 | 說明 | 範例 |
|------|------|------|
| `payload_size` | 每個封包的有效負載大小 (bytes) | 1024 |
| `protocol` | 傳輸協定 | tcp/udp/http |

### 配置建議

1. **CPU 核心數**：Server 端通常需要比 Client 端更多核心，建議 server_cpu_core ≥ client_cpu_core
2. **測試時間**：Server 端應比 Client 端多執行數秒，以確保完整接收所有流量
3. **記憶體配置**：socket_mem 應根據併發連線數和封包大小調整，建議至少 1024 MB
4. **併發連線數**：cc 值會影響資源使用，應根據測試目標和系統能力設定
5. **RSS 設定**：多核心環境下建議啟用 RSS 以提升效能

### 多組 Pair 配置

若需測試多組網卡對，可在 `pairs` 清單中添加多個配置區塊：

```yaml
pairs:
  - client:
      client_nic_pci: 0000:b6:00.0
      # ... 其他配置
    server:
      server_nic_pci: 0000:b6:00.1
      # ... 其他配置

  - client:
      client_nic_pci: 0000:b7:00.0
      # ... 第二組配置
    server:
      server_nic_pci: 0000:b7:00.1
      # ... 第二組配置
```

---

## 系統需求

- Python 3.7+
- paramiko（SSH 連接庫）
- 遠端主機需安裝 DPDK 和 DPerf
- 遠端主機需支援 hugepages 和 DPDK 驅動

## 注意事項

1. **權限要求**：部分操作（如綁定 NIC、設定 hugepages）需要 sudo 權限
2. **多線程安全**：目前 SignalHandler 的中斷功能已暫時關閉以避免多線程衝突
3. **持久 Session**：使用持久 session 可保持狀態，適合需要多個連續命令的場景
4. **日誌管理**：每個測試對會產生獨立的日誌檔案，便於問題追蹤
5. **資源清理**：建議使用 with 語句或確保呼叫 close() 方法以正確釋放資源

## 授權

請參考專案授權文件。

<!-- FUNCTION_SCAN_BEGIN -->
## 專案函式掃描結果

> 掃描到 **8** 個 Python 檔案，共 **18** 個 class、**5** 個 top-level function、**93** 個 method (總計 **98** 個 function)

| 檔案 | Classes | Top-level Functions | Methods | 合計 |
|------|---------|--------------------:|--------:|-----:|
| `APVSetup.py` | 1 | 1 | 10 | 11 |
| `RedisDB.py` | 1 | 0 | 11 | 11 |
| `config.py` | 7 | 0 | 3 | 3 |
| `dperfSetup.py` | 1 | 1 | 18 | 19 |
| `main.py` | 0 | 3 | 0 | 3 |
| `output_handler.py` | 1 | 0 | 11 | 11 |
| `ssh_executor.py` | 6 | 0 | 30 | 30 |
| `trafficGenerator.py` | 1 | 0 | 10 | 10 |

### `APVSetup.py`

**Top-level Functions:**

- `argParser()` (line 184)

**Class `APVSetup`** (line 5):

- `__init__()` (line 6)
- `__del__()` (line 21)
- `_execute_commands()` (line 28)
- `setupUDPLoadBalancer()` (line 37)
- `setupTCPLoadBalancer()` (line 73)
- `setupHTTPLoadBalancer()` (line 104)
- `setupEnv()` (line 136)
- `clearEnv()` (line 157)
- `connect()` (line 178)
- `disconnect()` (line 181)

### `RedisDB.py`

**Class `RedisHandler`** (line 9):

- `__init__()` (line 12)
- `is_connected()` (line 50)
- `save_monitor_data()` (line 54)
- `save_test_output()` (line 101)
- `get_monitor_data()` (line 154)
- `get_test_output()` (line 196)
- `clear_pair_data()` (line 248)
- `get_all_test_outputs()` (line 279)
- `get_specific_metrics()` (line 338)
- `get_pair_summary()` (line 383)
- `close()` (line 421)

### `config.py`

**Class `Client`** (line 6):

- _(no methods)_

**Class `ClientConfig`** (line 14):

- _(no methods)_

**Class `ServerConfig`** (line 36):

- _(no methods)_

**Class `TrafficGeneratorPair`** (line 54):

- _(no methods)_

**Class `TrafficGenerator`** (line 63):

- _(no methods)_

**Class `TestConfig`** (line 77):

- _(no methods)_

**Class `Config`** (line 87):

- `__init__()` (line 89)
- `from_yaml()` (line 100)
- `to_dict()` (line 191)

### `dperfSetup.py`

**Top-level Functions:**

- `argParser()` (line 551)

**Class `dperf`** (line 12):

- `__init__()` (line 13)
- `__del__()` (line 64)
- `connect()` (line 71)
- `disconnect()` (line 77)
- `generateServerConfig()` (line 87)
- `generateClientConfig()` (line 125)
- `runPairTest()` (line 166)
- `outputResults()` (line 198)
- `serverStart()` (line 297)
- `clientStart()` (line 337)
- `parseOutput()` (line 380)
- `bindNICs()` (line 430)
- `unbindNICs()` (line 452)
- `setHugePages()` (line 478)
- `setupConfig()` (line 500)
- `setupEnv()` (line 521)
- `get_redis_summary()` (line 535)
- `get_redis_test_output()` (line 543)

### `main.py`

**Top-level Functions:**

- `parse_arguments()` (line 9)
- `argOverrideConfig()` (line 72)
- `main()` (line 94)

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

### `trafficGenerator.py`

**Class `TrafficGenerator`** (line 9):

- `__init__()` (line 16)
- `connect()` (line 71)
- `disconnect()` (line 86)
- `setup_env()` (line 101)
- `run_test()` (line 122)
- `_run_sequential()` (line 165)
- `_run_parallel()` (line 184)
- `get_pair()` (line 213)
- `get_monitor()` (line 226)
- `get_pair_count()` (line 234)

<!-- FUNCTION_SCAN_END -->
