from config import Config
from dperfSetup import dperf
from system_monitor import SystemMonitor
from threading import Thread
from concurrent.futures import ThreadPoolExecutor
import time


class TrafficGenerator:
    """流量產生器管理類別

    封裝多組 dperf pair 和一個共用的 SystemMonitor，
    提供統一的介面來管理流量測試。
    """

    def __init__(self, config: Config, log_path: str = "./logs", output_path: str = "./results",
                 redis_host: str = "localhost", redis_port: int = 6379, redis_db: int = 0,
                 enable_redis: bool = True):
        """初始化流量產生器

        Args:
            config: 配置物件
            log_path: 日誌輸出路徑
            output_path: 結果輸出路徑
            redis_host: Redis 主機位址
            redis_port: Redis 埠號
            redis_db: Redis 資料庫編號
            enable_redis: 是否啟用 Redis 儲存
        """
        self.config = config
        self.log_path = log_path
        self.output_path = output_path
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.enable_redis = enable_redis

        # 取得 pair 數量
        self.pair_count = len(config.test.traffic_generator.pairs)
        print(f"[TrafficGenerator] 偵測到 {self.pair_count} 組 pair")

        # 建立共用的 SystemMonitor（整台機器只需一個）
        self.monitor = SystemMonitor(
            management_ip=config.test.traffic_generator.management_ip,
            management_port=config.test.traffic_generator.management_port,
            username=config.test.traffic_generator.username,
            password=config.test.traffic_generator.password,
            log_path=log_path,
            redis_host=redis_host,
            redis_port=redis_port,
            redis_db=redis_db,
            enable_redis=enable_redis
        )

        # 建立多組 dperf pair
        self.pairs = []
        for i in range(self.pair_count):
            pair = dperf(
                config=config,
                pair_index=i,
                log_path=log_path,
                output_path=f"{output_path}/dperf_pair{i}_results.csv",
                redis_host=redis_host,
                redis_port=redis_port,
                redis_db=redis_db,
                enable_redis=enable_redis
            )
            self.pairs.append(pair)
            print(f"[TrafficGenerator] 已建立 Pair {i}")

    def connect(self):
        """連接到遠端主機（包含 monitor 和所有 pair）"""
        print("[TrafficGenerator] 開始連接...")

        # 連接 monitor
        self.monitor.connect()
        print("[TrafficGenerator] Monitor 已連接")

        # 連接所有 pair
        for i, pair in enumerate(self.pairs):
            pair.connect()
            print(f"[TrafficGenerator] Pair {i} 已連接")

        print("[TrafficGenerator] 所有連接已建立")

    def disconnect(self):
        """斷開所有連接"""
        print("[TrafficGenerator] 開始斷開連接...")

        # 斷開所有 pair
        for i, pair in enumerate(self.pairs):
            pair.disconnect()
            print(f"[TrafficGenerator] Pair {i} 已斷開")

        # 斷開 monitor
        self.monitor.disconnect()
        print("[TrafficGenerator] Monitor 已斷開")

        print("[TrafficGenerator] 所有連接已斷開")

    def setup_env(self, pair_indices: list = None):
        """設定測試環境

        Args:
            pair_indices: 要設定的 pair 索引列表，若為 None 則設定所有 pair
        """
        if pair_indices is None:
            pair_indices = list(range(self.pair_count))

        print(f"[TrafficGenerator] 開始設定環境 (Pairs: {pair_indices})...")

        for i in pair_indices:
            if i < len(self.pairs):
                print(f"[TrafficGenerator] 設定 Pair {i} 環境...")
                self.pairs[i].setupEnv()
                print(f"[TrafficGenerator] Pair {i} 環境設定完成")
            else:
                print(f"[TrafficGenerator] 警告: Pair {i} 不存在")

        print("[TrafficGenerator] 環境設定完成")

    def run_test(self, pair_indices: list = None, enable_monitor: bool = True,
                 parallel: bool = False, monitor_output_file: str = None):
        """執行測試

        Args:
            pair_indices: 要測試的 pair 索引列表，若為 None 則測試所有 pair
            enable_monitor: 是否啟用監控
            parallel: 是否並行執行多組 pair 測試
            monitor_output_file: 監控數據輸出檔案路徑

        Returns:
            dict: 測試結果，包含各 pair 的 server/client 輸出和監控數據
        """
        if pair_indices is None:
            pair_indices = list(range(self.pair_count))

        print(f"[TrafficGenerator] 開始測試 (Pairs: {pair_indices}, 並行: {parallel}, 監控: {enable_monitor})...")

        results = {}

        # 啟動監控
        if enable_monitor:
            self.monitor.start(output_file=monitor_output_file)
            time.sleep(2)  # 確保監控已啟動

        try:
            if parallel:
                # 並行執行所有 pair 測試
                results = self._run_parallel(pair_indices)
            else:
                # 順序執行各 pair 測試
                results = self._run_sequential(pair_indices)
        finally:
            # 停止監控
            if enable_monitor:
                self.monitor.stop()

        # 加入監控數據到結果
        results['monitor_data'] = self.monitor.get_data()

        print("[TrafficGenerator] 測試完成")
        return results

    def _run_sequential(self, pair_indices: list):
        """順序執行測試

        Args:
            pair_indices: 要測試的 pair 索引列表

        Returns:
            dict: 測試結果
        """
        results = {}
        for i in pair_indices:
            if i < len(self.pairs):
                print(f"[TrafficGenerator] 執行 Pair {i} 測試...")
                result = self.pairs[i].runPairTest(monitor=self.monitor)
                results[f'pair_{i}'] = result
            else:
                print(f"[TrafficGenerator] 警告: Pair {i} 不存在")
        return results

    def _run_parallel(self, pair_indices: list):
        """並行執行測試

        Args:
            pair_indices: 要測試的 pair 索引列表

        Returns:
            dict: 測試結果
        """
        results = {}
        threads = []

        def run_pair(pair_index):
            if pair_index < len(self.pairs):
                result = self.pairs[pair_index].runPairTest(monitor=self.monitor)
                results[f'pair_{pair_index}'] = result

        # 建立並啟動所有測試執行緒
        for i in pair_indices:
            t = Thread(target=run_pair, args=(i,), name=f"PairTest-{i}")
            threads.append(t)
            t.start()

        # 等待所有執行緒完成
        for t in threads:
            t.join()

        return results

    def get_pair(self, pair_index: int):
        """取得指定的 pair 實例

        Args:
            pair_index: pair 索引

        Returns:
            dperf: pair 實例，若索引無效則返回 None
        """
        if 0 <= pair_index < len(self.pairs):
            return self.pairs[pair_index]
        return None

    def get_monitor(self):
        """取得 monitor 實例

        Returns:
            SystemMonitor: monitor 實例
        """
        return self.monitor

    def get_pair_count(self):
        """取得 pair 數量

        Returns:
            int: pair 數量
        """
        return self.pair_count
