# Array Script - DPerf 測試自動化工具

此專案提供自動化腳本來執行 DPerf 網路效能測試，透過 SSH 連接遠端主機，自動配置 DPDK 環境並運行測試。

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
