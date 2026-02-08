#!/usr/bin/env python3
"""Redis Database Handler - Used for storing test data"""

import redis as redis_client
from typing import Optional, Dict, List
from datetime import datetime


class RedisHandler:
    """Redis Database Handler"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        decode_responses: bool = True,
    ):
        """
        Initialize Redis connection

        Args:
            host: Redis host address
            port: Redis port
            db: Redis database index
            password: Redis password (if required)
            decode_responses: Whether to automatically decode responses to strings
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
            # Test connection
            self.client.ping()
            print(f"Successfully connected to Redis: {host}:{port}")
        except Exception as e:
            print(f"Warning: Unable to connect to Redis ({host}:{port}): {e}")
            self.client = None

    def is_connected(self) -> bool:
        """Check if connected to Redis successfully"""
        return self.client is not None

    def save_monitor_data(
        self, pair_index: int, timestamp: str, cpu_usage: float,
        ram_used: int, ram_total: int, ram_usage: float
    ) -> bool:
        """
        Store monitoring data to Redis

        Args:
            pair_index: pair index
            timestamp: Timestamp
            cpu_usage: CPU usage
            ram_used: RAM used (MB)
            ram_total: Total RAM (MB)
            ram_usage: RAM usage

        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            return False

        try:
            # Use Hash structure to store monitoring data
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

            # Add key to sorted set for time-sorted queries
            # Score uses timestamp converted to Unix timestamp
            ts = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S').timestamp()
            self.client.zadd(f"monitor:pair{pair_index}:timeline", {key: ts})

            return True
        except Exception as e:
            print(f"Failed to store monitoring data: {e}")
            return False

    def save_test_output(
        self, pair_index: int, role: str, output: Dict, timestamp: Optional[str] = None
    ) -> bool:
        """
        Store test output data (server or client)

        Data structure:
        - test:pair{index}:{role}:{timestamp}:info - Store metadata (pair_index, role, timestamp)
        - test:pair{index}:{role}:{timestamp}:metrics - Store all performance metrics (duration, ackDup, etc.)

        Args:
            pair_index: pair index
            role: Role ('server' or 'client')
            output: Test output data dictionary
            timestamp: Timestamp (optional, default uses current time)

        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            return False

        if timestamp is None:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            # Key prefix
            key_prefix = f"test:pair{pair_index}:{role}:{timestamp}"

            # 1. Store metadata
            info_key = f"{key_prefix}:info"
            metadata = {
                "pair_index": pair_index,
                "role": role,
                "timestamp": timestamp,
            }
            self.client.hset(info_key, mapping=metadata)

            # 2. Store metrics
            metrics_key = f"{key_prefix}:metrics"
            # Store all output data as metrics
            metrics_data = {k: str(v) for k, v in output.items()}
            self.client.hset(metrics_key, mapping=metrics_data)

            # 3. Add key prefix to sorted set for time-sorted queries
            ts = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S').timestamp()
            self.client.zadd(f"test:pair{pair_index}:{role}:timeline", {key_prefix: ts})

            return True
        except Exception as e:
            print(f"Failed to store test output: {e}")
            return False

    def get_monitor_data(
        self, pair_index: int, start_time: Optional[str] = None, end_time: Optional[str] = None
    ) -> List[Dict]:
        """
        Retrieve monitoring data

        Args:
            pair_index: pair index
            start_time: Start time (optional)
            end_time: End time (optional)

        Returns:
            Monitoring data list
        """
        if not self.is_connected():
            return []

        try:
            # Get keys within time range from sorted set
            min_score = '-inf'
            max_score = '+inf'

            if start_time:
                min_score = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S').timestamp()
            if end_time:
                max_score = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S').timestamp()

            keys = self.client.zrangebyscore(
                f"monitor:pair{pair_index}:timeline", min_score, max_score
            )

            # Retrieve data for each key
            result = []
            for key in keys:
                data = self.client.hgetall(key)
                result.append(data)

            return result
        except Exception as e:
            print(f"Failed to retrieve monitoring data: {e}")
            return []

    def get_test_output(
        self, pair_index: int, role: str, timestamp: Optional[str] = None,
        include_metrics: bool = True
    ) -> Optional[Dict]:
        """
        Retrieve test output data

        Args:
            pair_index: pair index
            role: Role ('server' or 'client')
            timestamp: Timestamp (optional, returns latest if not provided)
            include_metrics: Whether to include metrics data (default True)

        Returns:
            Test output dictionary containing 'info' and 'metrics' (if include_metrics=True)
            Returns None if not found
        """
        if not self.is_connected():
            return None

        try:
            if timestamp is None:
                # Retrieve latest data
                key_prefixes = self.client.zrevrange(
                    f"test:pair{pair_index}:{role}:timeline", 0, 0
                )
                if not key_prefixes:
                    return None
                key_prefix = key_prefixes[0]
            else:
                key_prefix = f"test:pair{pair_index}:{role}:{timestamp}"

            # Read metadata
            info_key = f"{key_prefix}:info"
            info_data = self.client.hgetall(info_key)

            if not info_data:
                return None

            result = {"info": info_data}

            # Read metrics (if required)
            if include_metrics:
                metrics_key = f"{key_prefix}:metrics"
                metrics_data = self.client.hgetall(metrics_key)
                result["metrics"] = metrics_data if metrics_data else {}

            return result
        except Exception as e:
            print(f"Failed to retrieve test output: {e}")
            return None

    def clear_pair_data(self, pair_index: int) -> bool:
        """
        Clear all data for specified pair

        Args:
            pair_index: pair index

        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            return False

        try:
            # Get all related keys
            patterns = [
                f"monitor:pair{pair_index}:*",
                f"test:pair{pair_index}:*",
            ]

            for pattern in patterns:
                keys = self.client.keys(pattern)
                if keys:
                    self.client.delete(*keys)

            print(f"Cleared all data for pair {pair_index}")
            return True
        except Exception as e:
            print(f"Failed to clear data: {e}")
            return False

    def get_all_test_outputs(
        self, pair_index: int, role: str, start_time: Optional[str] = None,
        end_time: Optional[str] = None, include_metrics: bool = True
    ) -> List[Dict]:
        """
        Retrieve all test output data within specified time range

        Args:
            pair_index: pair index
            role: Role ('server' or 'client')
            start_time: Start time (optional)
            end_time: End time (optional)
            include_metrics: Whether to include metrics data (default True)

        Returns:
            Test output list, each element containing 'info' and 'metrics' (if include_metrics=True)
        """
        if not self.is_connected():
            return []

        try:
            # Get key prefixes within time range from sorted set
            min_score = '-inf'
            max_score = '+inf'

            if start_time:
                min_score = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S').timestamp()
            if end_time:
                max_score = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S').timestamp()

            key_prefixes = self.client.zrangebyscore(
                f"test:pair{pair_index}:{role}:timeline", min_score, max_score
            )

            # Retrieve data for each key prefix
            result = []
            for key_prefix in key_prefixes:
                # Read metadata
                info_key = f"{key_prefix}:info"
                info_data = self.client.hgetall(info_key)

                if not info_data:
                    continue

                data = {"info": info_data}

                # Read metrics (if required)
                if include_metrics:
                    metrics_key = f"{key_prefix}:metrics"
                    metrics_data = self.client.hgetall(metrics_key)
                    data["metrics"] = metrics_data if metrics_data else {}

                result.append(data)

            return result
        except Exception as e:
            print(f"Failed to retrieve test output data: {e}")
            return []

    def get_specific_metrics(
        self, pair_index: int, role: str, metric_names: List[str],
        timestamp: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Retrieve specific metrics data

        Args:
            pair_index: pair index
            role: Role ('server' or 'client')
            metric_names: List of metric names to query (e.g. ['duration', 'ackDup', 'synRt'])
            timestamp: Timestamp (optional, returns latest if not provided)

        Returns:
            Dictionary containing specified metrics, returns None if not found
            Format: {'duration': 'value', 'ackDup': 'value', ...}
        """
        if not self.is_connected():
            return None

        try:
            if timestamp is None:
                # Retrieve latest data
                key_prefixes = self.client.zrevrange(
                    f"test:pair{pair_index}:{role}:timeline", 0, 0
                )
                if not key_prefixes:
                    return None
                key_prefix = key_prefixes[0]
            else:
                key_prefix = f"test:pair{pair_index}:{role}:{timestamp}"

            # Read specified metrics
            metrics_key = f"{key_prefix}:metrics"
            result = {}

            for metric_name in metric_names:
                value = self.client.hget(metrics_key, metric_name)
                result[metric_name] = value if value is not None else None

            return result
        except Exception as e:
            print(f"Failed to retrieve specific metrics: {e}")
            return None

    def get_pair_summary(self, pair_index: int) -> Dict:
        """
        Retrieve data summary for specified pair

        Args:
            pair_index: pair index

        Returns:
            Summary dictionary containing monitor data and test output counts
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

            # Retrieve monitor data count
            monitor_keys = self.client.zcard(f"monitor:pair{pair_index}:timeline")
            summary['monitor_count'] = monitor_keys if monitor_keys else 0

            # Retrieve server output count
            server_keys = self.client.zcard(f"test:pair{pair_index}:server:timeline")
            summary['server_output_count'] = server_keys if server_keys else 0

            # Retrieve client output count
            client_keys = self.client.zcard(f"test:pair{pair_index}:client:timeline")
            summary['client_output_count'] = client_keys if client_keys else 0

            return summary
        except Exception as e:
            print(f"Failed to retrieve pair summary: {e}")
            return {}

    def close(self) -> None:
        """Close Redis connection"""
        if self.client:
            self.client.close()
            print("Redis connection closed")

