#!/usr/bin/env python3
"""Redis 資料庫處理器 - 用於儲存測試數據"""

import redis as redis_client
from typing import Optional, Dict, List
from datetime import datetime


class RedisHandler:
    """Redis 資料庫處理器"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        decode_responses: bool = True,
    ):
        """
        初始化 Redis 連接

        Args:
            host: Redis 主機地址
            port: Redis 端口
            db: Redis 數據庫編號
            password: Redis 密碼（如果需要）
            decode_responses: 是否自動解碼響應為字符串
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password

        try:
            self.client = redis_client.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=decode_responses,
            )
            # 測試連接
            self.client.ping()
            print(f"成功連接到 Redis: {host}:{port}")
        except Exception as e:
            print(f"警告: 無法連接到 Redis ({host}:{port}): {e}")
            self.client = None

    def is_connected(self) -> bool:
        """檢查是否成功連接到 Redis"""
        return self.client is not None

    def save_monitor_data(
        self, pair_index: int, timestamp: str, cpu_usage: float,
        ram_used: int, ram_total: int, ram_usage: float
    ) -> bool:
        """
        儲存監控數據到 Redis

        Args:
            pair_index: pair 索引
            timestamp: 時間戳
            cpu_usage: CPU 使用率
            ram_used: 已使用 RAM (MB)
            ram_total: 總 RAM (MB)
            ram_usage: RAM 使用率

        Returns:
            成功返回 True，否則返回 False
        """
        if not self.is_connected():
            return False

        try:
            # 使用 Hash 結構儲存監控數據
            # Key: monitor:pair{index}:{timestamp}
            key = f"monitor:pair{pair_index}:{timestamp}"

            data = {
                "pair_index": pair_index,
                "timestamp": timestamp,
                "cpu_usage": cpu_usage,
                "ram_used": ram_used,
                "ram_total": ram_total,
                "ram_usage": ram_usage,
            }

            self.client.hset(key, mapping=data)

            # 將 key 加入到 sorted set 以便按時間排序查詢
            # Score 使用時間戳轉換為 Unix 時間戳
            ts = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S').timestamp()
            self.client.zadd(f"monitor:pair{pair_index}:timeline", {key: ts})

            return True
        except Exception as e:
            print(f"儲存監控數據失敗: {e}")
            return False

    def save_test_output(
        self, pair_index: int, role: str, output: Dict, timestamp: Optional[str] = None
    ) -> bool:
        """
        儲存測試輸出數據（server 或 client）

        資料結構：
        - test:pair{index}:{role}:{timestamp}:info - 儲存 metadata (pair_index, role, timestamp)
        - test:pair{index}:{role}:{timestamp}:metrics - 儲存所有效能指標 (duration, ackDup, etc.)

        Args:
            pair_index: pair 索引
            role: 角色 ('server' 或 'client')
            output: 測試輸出數據字典
            timestamp: 時間戳（可選，預設使用當前時間）

        Returns:
            成功返回 True，否則返回 False
        """
        if not self.is_connected():
            return False

        if timestamp is None:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            # Key 前綴
            key_prefix = f"test:pair{pair_index}:{role}:{timestamp}"

            # 1. 儲存 metadata
            info_key = f"{key_prefix}:info"
            metadata = {
                "pair_index": pair_index,
                "role": role,
                "timestamp": timestamp,
            }
            self.client.hset(info_key, mapping=metadata)

            # 2. 儲存 metrics
            metrics_key = f"{key_prefix}:metrics"
            # 將所有 output 數據作為 metrics 儲存
            metrics_data = {k: str(v) for k, v in output.items()}
            self.client.hset(metrics_key, mapping=metrics_data)

            # 3. 將 key 前綴加入到 sorted set 以便按時間排序查詢
            ts = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S').timestamp()
            self.client.zadd(f"test:pair{pair_index}:{role}:timeline", {key_prefix: ts})

            return True
        except Exception as e:
            print(f"儲存測試輸出失敗: {e}")
            return False

    def get_monitor_data(
        self, pair_index: int, start_time: Optional[str] = None, end_time: Optional[str] = None
    ) -> List[Dict]:
        """
        獲取監控數據

        Args:
            pair_index: pair 索引
            start_time: 起始時間（可選）
            end_time: 結束時間（可選）

        Returns:
            監控數據列表
        """
        if not self.is_connected():
            return []

        try:
            # 從 sorted set 獲取時間範圍內的 keys
            min_score = '-inf'
            max_score = '+inf'

            if start_time:
                min_score = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S').timestamp()
            if end_time:
                max_score = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S').timestamp()

            keys = self.client.zrangebyscore(
                f"monitor:pair{pair_index}:timeline", min_score, max_score
            )

            # 獲取每個 key 的數據
            result = []
            for key in keys:
                data = self.client.hgetall(key)
                result.append(data)

            return result
        except Exception as e:
            print(f"獲取監控數據失敗: {e}")
            return []

    def get_test_output(
        self, pair_index: int, role: str, timestamp: Optional[str] = None,
        include_metrics: bool = True
    ) -> Optional[Dict]:
        """
        獲取測試輸出數據

        Args:
            pair_index: pair 索引
            role: 角色 ('server' 或 'client')
            timestamp: 時間戳（可選，若不提供則返回最新的）
            include_metrics: 是否包含 metrics 數據（預設 True）

        Returns:
            測試輸出數據字典，包含 'info' 和 'metrics' (如果 include_metrics=True)
            如果不存在則返回 None
        """
        if not self.is_connected():
            return None

        try:
            if timestamp is None:
                # 獲取最新的數據
                key_prefixes = self.client.zrevrange(
                    f"test:pair{pair_index}:{role}:timeline", 0, 0
                )
                if not key_prefixes:
                    return None
                key_prefix = key_prefixes[0]
            else:
                key_prefix = f"test:pair{pair_index}:{role}:{timestamp}"

            # 讀取 metadata
            info_key = f"{key_prefix}:info"
            info_data = self.client.hgetall(info_key)

            if not info_data:
                return None

            result = {"info": info_data}

            # 讀取 metrics (如果需要)
            if include_metrics:
                metrics_key = f"{key_prefix}:metrics"
                metrics_data = self.client.hgetall(metrics_key)
                result["metrics"] = metrics_data if metrics_data else {}

            return result
        except Exception as e:
            print(f"獲取測試輸出失敗: {e}")
            return None

    def clear_pair_data(self, pair_index: int) -> bool:
        """
        清除指定 pair 的所有數據

        Args:
            pair_index: pair 索引

        Returns:
            成功返回 True，否則返回 False
        """
        if not self.is_connected():
            return False

        try:
            # 獲取所有相關的 keys
            patterns = [
                f"monitor:pair{pair_index}:*",
                f"test:pair{pair_index}:*",
            ]

            for pattern in patterns:
                keys = self.client.keys(pattern)
                if keys:
                    self.client.delete(*keys)

            print(f"已清除 pair {pair_index} 的所有數據")
            return True
        except Exception as e:
            print(f"清除數據失敗: {e}")
            return False

    def get_all_test_outputs(
        self, pair_index: int, role: str, start_time: Optional[str] = None,
        end_time: Optional[str] = None, include_metrics: bool = True
    ) -> List[Dict]:
        """
        獲取指定時間範圍內的所有測試輸出數據

        Args:
            pair_index: pair 索引
            role: 角色 ('server' 或 'client')
            start_time: 起始時間（可選）
            end_time: 結束時間（可選）
            include_metrics: 是否包含 metrics 數據（預設 True）

        Returns:
            測試輸出數據列表，每個元素包含 'info' 和 'metrics' (如果 include_metrics=True)
        """
        if not self.is_connected():
            return []

        try:
            # 從 sorted set 獲取時間範圍內的 key prefixes
            min_score = '-inf'
            max_score = '+inf'

            if start_time:
                min_score = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S').timestamp()
            if end_time:
                max_score = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S').timestamp()

            key_prefixes = self.client.zrangebyscore(
                f"test:pair{pair_index}:{role}:timeline", min_score, max_score
            )

            # 獲取每個 key prefix 的數據
            result = []
            for key_prefix in key_prefixes:
                # 讀取 metadata
                info_key = f"{key_prefix}:info"
                info_data = self.client.hgetall(info_key)

                if not info_data:
                    continue

                data = {"info": info_data}

                # 讀取 metrics (如果需要)
                if include_metrics:
                    metrics_key = f"{key_prefix}:metrics"
                    metrics_data = self.client.hgetall(metrics_key)
                    data["metrics"] = metrics_data if metrics_data else {}

                result.append(data)

            return result
        except Exception as e:
            print(f"獲取測試輸出數據失敗: {e}")
            return []

    def get_specific_metrics(
        self, pair_index: int, role: str, metric_names: List[str],
        timestamp: Optional[str] = None
    ) -> Optional[Dict]:
        """
        獲取特定的 metrics 數據

        Args:
            pair_index: pair 索引
            role: 角色 ('server' 或 'client')
            metric_names: 要查詢的 metric 名稱列表 (例如 ['duration', 'ackDup', 'synRt'])
            timestamp: 時間戳（可選，若不提供則返回最新的）

        Returns:
            包含指定 metrics 的字典，如果不存在則返回 None
            格式: {'duration': '值', 'ackDup': '值', ...}
        """
        if not self.is_connected():
            return None

        try:
            if timestamp is None:
                # 獲取最新的數據
                key_prefixes = self.client.zrevrange(
                    f"test:pair{pair_index}:{role}:timeline", 0, 0
                )
                if not key_prefixes:
                    return None
                key_prefix = key_prefixes[0]
            else:
                key_prefix = f"test:pair{pair_index}:{role}:{timestamp}"

            # 讀取指定的 metrics
            metrics_key = f"{key_prefix}:metrics"
            result = {}

            for metric_name in metric_names:
                value = self.client.hget(metrics_key, metric_name)
                result[metric_name] = value if value is not None else None

            return result
        except Exception as e:
            print(f"獲取特定 metrics 失敗: {e}")
            return None

    def get_pair_summary(self, pair_index: int) -> Dict:
        """
        獲取指定 pair 的數據摘要

        Args:
            pair_index: pair 索引

        Returns:
            包含監控數據和測試輸出數量的摘要字典
        """
        if not self.is_connected():
            return {}

        try:
            summary = {
                'pair_index': pair_index,
                'monitor_count': 0,
                'server_output_count': 0,
                'client_output_count': 0,
            }

            # 獲取監控數據數量
            monitor_keys = self.client.zcard(f"monitor:pair{pair_index}:timeline")
            summary['monitor_count'] = monitor_keys if monitor_keys else 0

            # 獲取 server 輸出數量
            server_keys = self.client.zcard(f"test:pair{pair_index}:server:timeline")
            summary['server_output_count'] = server_keys if server_keys else 0

            # 獲取 client 輸出數量
            client_keys = self.client.zcard(f"test:pair{pair_index}:client:timeline")
            summary['client_output_count'] = client_keys if client_keys else 0

            return summary
        except Exception as e:
            print(f"獲取 pair 摘要失敗: {e}")
            return {}

    def close(self) -> None:
        """關閉 Redis 連接"""
        if self.client:
            self.client.close()
            print("Redis 連接已關閉")

