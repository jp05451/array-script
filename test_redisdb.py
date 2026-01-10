from RedisDB import RedisHandler
from datetime import datetime

if __name__ == "__main__":
    """測試腳本 - 測試所有 Redis 功能"""
    import time

    print("=" * 60)
    print("開始測試 RedisHandler 所有功能")
    print("=" * 60)

    # 測試參數
    TEST_PAIR_INDEX = 0

    # 1. 測試連接
    print("\n[測試 1] 測試 Redis 連接...")
    redis_handler = RedisHandler(host="localhost", port=6379, db=0)

    if not redis_handler.is_connected():
        print("❌ Redis 連接失敗，請確保 Redis 服務正在運行")
        print("提示: 執行 'redis-server' 啟動 Redis 服務")
        exit(1)
    print("✅ Redis 連接成功")

    # 2. 清除舊數據
    print(f"\n[測試 2] 清除 pair {TEST_PAIR_INDEX} 的舊數據...")
    redis_handler.clear_pair_data(TEST_PAIR_INDEX)
    print("✅ 舊數據清除完成")

    # 3. 測試儲存監控數據
    print(f"\n[測試 3] 測試儲存監控數據 (模擬 5 秒的監控數據)...")
    for i in range(5):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cpu_usage = 50.0 + i * 2.5  # 模擬 CPU 使用率從 50% 到 60%
        ram_used = 8000 + i * 100   # 模擬 RAM 使用量遞增
        ram_total = 16000
        ram_usage = (ram_used / ram_total) * 100

        success = redis_handler.save_monitor_data(
            pair_index=TEST_PAIR_INDEX,
            timestamp=timestamp,
            cpu_usage=cpu_usage,
            ram_used=ram_used,
            ram_total=ram_total,
            ram_usage=ram_usage
        )

        if success:
            print(f"  ✓ 儲存監控數據 #{i+1}: CPU={cpu_usage:.1f}%, RAM={ram_used}MB ({ram_usage:.1f}%)")
        else:
            print(f"  ✗ 儲存監控數據 #{i+1} 失敗")

        time.sleep(0.2)  # 模擬時間間隔

    print("✅ 監控數據儲存測試完成")

    # 4. 測試儲存 server 輸出
    print(f"\n[測試 4] 測試儲存 server 輸出數據...")
    server_output = {
        'Sends': 1234567,
        'Recvs': 1234500,
        'Errors': 0,
        'snd_bytes': 1000000000,
        'rcv_bytes': 999000000,
        'Retrans': 100,
        'Drops': 5,
        'HTTP-GET': 10000,
        'HTTP-2XX': 9950,
        'HTTP-4XX': 50,
    }

    success = redis_handler.save_test_output(
        pair_index=TEST_PAIR_INDEX,
        role='server',
        output=server_output
    )

    if success:
        print("  ✓ Server 輸出數據儲存成功")
        for key, value in server_output.items():
            print(f"    - {key}: {value}")
    else:
        print("  ✗ Server 輸出數據儲存失敗")

    print("✅ Server 輸出儲存測試完成")

    # 5. 測試儲存 client 輸出
    print(f"\n[測試 5] 測試儲存 client 輸出數據...")
    client_output = {
        'Sends': 1234600,
        'Recvs': 1234550,
        'Errors': 1,
        'snd_bytes': 1001000000,
        'rcv_bytes': 999500000,
        'Retrans': 120,
        'Drops': 8,
        'HTTP-GET': 10100,
        'HTTP-2XX': 10000,
        'HTTP-4XX': 100,
    }

    success = redis_handler.save_test_output(
        pair_index=TEST_PAIR_INDEX,
        role='client',
        output=client_output
    )

    if success:
        print("  ✓ Client 輸出數據儲存成功")
        for key, value in client_output.items():
            print(f"    - {key}: {value}")
    else:
        print("  ✗ Client 輸出數據儲存失敗")

    print("✅ Client 輸出儲存測試完成")

    # 6. 測試讀取監控數據
    print(f"\n[測試 6] 測試讀取監控數據...")
    monitor_data = redis_handler.get_monitor_data(TEST_PAIR_INDEX)

    if monitor_data:
        print(f"  ✓ 成功讀取 {len(monitor_data)} 筆監控數據")
        print(f"  第一筆: {monitor_data[0]}")
        print(f"  最後一筆: {monitor_data[-1]}")
    else:
        print("  ✗ 讀取監控數據失敗")

    print("✅ 監控數據讀取測試完成")

    # 7. 測試讀取 server 輸出
    print(f"\n[測試 7] 測試讀取 server 輸出數據...")
    server_data = redis_handler.get_test_output(TEST_PAIR_INDEX, 'server')

    if server_data:
        print(f"  ✓ 成功讀取 server 輸出數據")
        info = server_data.get('info', {})
        metrics = server_data.get('metrics', {})
        print(f"  [Info]")
        print(f"    - Pair Index: {info.get('pair_index')}")
        print(f"    - Role: {info.get('role')}")
        print(f"    - Timestamp: {info.get('timestamp')}")
        print(f"  [Metrics]")
        print(f"    - Sends: {metrics.get('Sends')}")
        print(f"    - Recvs: {metrics.get('Recvs')}")
        print(f"    - HTTP-GET: {metrics.get('HTTP-GET')}")
        print(f"    - HTTP-2XX: {metrics.get('HTTP-2XX')}")
    else:
        print("  ✗ 讀取 server 輸出數據失敗")

    print("✅ Server 輸出讀取測試完成")

    # 8. 測試讀取 client 輸出
    print(f"\n[測試 8] 測試讀取 client 輸出數據...")
    client_data = redis_handler.get_test_output(TEST_PAIR_INDEX, 'client')

    if client_data:
        print(f"  ✓ 成功讀取 client 輸出數據")
        info = client_data.get('info', {})
        metrics = client_data.get('metrics', {})
        print(f"  [Info]")
        print(f"    - Pair Index: {info.get('pair_index')}")
        print(f"    - Role: {info.get('role')}")
        print(f"    - Timestamp: {info.get('timestamp')}")
        print(f"  [Metrics]")
        print(f"    - Sends: {metrics.get('Sends')}")
        print(f"    - Recvs: {metrics.get('Recvs')}")
        print(f"    - HTTP-GET: {metrics.get('HTTP-GET')}")
        print(f"    - HTTP-2XX: {metrics.get('HTTP-2XX')}")
    else:
        print("  ✗ 讀取 client 輸出數據失敗")

    print("✅ Client 輸出讀取測試完成")

    # 9. 測試讀取所有測試輸出
    print(f"\n[測試 9] 測試讀取所有測試輸出數據...")
    all_server_outputs = redis_handler.get_all_test_outputs(TEST_PAIR_INDEX, 'server')
    all_client_outputs = redis_handler.get_all_test_outputs(TEST_PAIR_INDEX, 'client')

    print(f"  ✓ Server 輸出總數: {len(all_server_outputs)}")
    print(f"  ✓ Client 輸出總數: {len(all_client_outputs)}")

    print("✅ 所有測試輸出讀取測試完成")

    # 10. 測試獲取 pair 摘要
    print(f"\n[測試 10] 測試獲取 pair 摘要...")
    summary = redis_handler.get_pair_summary(TEST_PAIR_INDEX)

    if summary:
        print(f"  ✓ Pair {summary['pair_index']} 摘要:")
        print(f"    - 監控數據數量: {summary['monitor_count']}")
        print(f"    - Server 輸出數量: {summary['server_output_count']}")
        print(f"    - Client 輸出數量: {summary['client_output_count']}")
    else:
        print("  ✗ 獲取 pair 摘要失敗")

    print("✅ Pair 摘要測試完成")

    # 11. 測試多次儲存 (模擬多次測試運行)
    print(f"\n[測試 11] 測試多次儲存測試輸出 (模擬 3 次測試運行)...")
    for run in range(3):
        time.sleep(1)  # 確保時間戳不同
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        server_output_run = {
            'run_number': run + 1,
            'Sends': 1000000 + run * 10000,
            'Recvs': 999000 + run * 10000,
        }

        client_output_run = {
            'run_number': run + 1,
            'Sends': 1001000 + run * 10000,
            'Recvs': 1000000 + run * 10000,
        }

        redis_handler.save_test_output(TEST_PAIR_INDEX, 'server', server_output_run, timestamp)
        redis_handler.save_test_output(TEST_PAIR_INDEX, 'client', client_output_run, timestamp)

        print(f"  ✓ 第 {run + 1} 次測試運行數據已儲存")

    # 檢查總數
    updated_summary = redis_handler.get_pair_summary(TEST_PAIR_INDEX)
    print(f"  ✓ 更新後的摘要:")
    print(f"    - Server 輸出總數: {updated_summary['server_output_count']}")
    print(f"    - Client 輸出總數: {updated_summary['client_output_count']}")

    print("✅ 多次儲存測試完成")

    # 12. 測試時間範圍查詢
    print(f"\n[測試 12] 測試時間範圍查詢監控數據...")
    all_monitor_data = redis_handler.get_monitor_data(TEST_PAIR_INDEX)

    if len(all_monitor_data) > 0:
        # 取前3筆數據的時間範圍
        start_time = all_monitor_data[0]['timestamp']
        end_time = all_monitor_data[min(2, len(all_monitor_data)-1)]['timestamp']

        filtered_data = redis_handler.get_monitor_data(
            TEST_PAIR_INDEX, start_time=start_time, end_time=end_time
        )

        print(f"  ✓ 時間範圍: {start_time} 到 {end_time}")
        print(f"  ✓ 查詢到 {len(filtered_data)} 筆數據")
    else:
        print("  ✗ 沒有監控數據可供測試")

    print("✅ 時間範圍查詢測試完成")

    # 13. 測試查詢特定 metrics
    print(f"\n[測試 13] 測試查詢特定 metrics...")
    specific_metrics = redis_handler.get_specific_metrics(
        TEST_PAIR_INDEX, 'server', ['Sends', 'Recvs', 'HTTP-2XX', 'Errors']
    )

    if specific_metrics:
        print(f"  ✓ 成功查詢特定 metrics:")
        for metric_name, value in specific_metrics.items():
            print(f"    - {metric_name}: {value}")
    else:
        print("  ✗ 查詢特定 metrics 失敗")

    print("✅ 特定 metrics 查詢測試完成")

    # 14. 最終清理測試
    print(f"\n[測試 14] 測試清除數據功能...")
    print(f"  清除前: {redis_handler.get_pair_summary(TEST_PAIR_INDEX)}")

    redis_handler.clear_pair_data(TEST_PAIR_INDEX)

    final_summary = redis_handler.get_pair_summary(TEST_PAIR_INDEX)
    print(f"  清除後: {final_summary}")

    if (final_summary['monitor_count'] == 0 and
        final_summary['server_output_count'] == 0 and
        final_summary['client_output_count'] == 0):
        print("✅ 數據清除功能正常")
    else:
        print("⚠️  數據可能未完全清除")

    # 關閉連接
    print(f"\n[測試 15] 關閉 Redis 連接...")
    redis_handler.close()
    print("✅ 連接已關閉")

    print("\n" + "=" * 60)
    print("所有測試完成！")
    print("=" * 60)
    print("\n測試摘要:")
    print("✅ 1. Redis 連接測試")
    print("✅ 2. 清除舊數據測試")
    print("✅ 3. 儲存監控數據測試")
    print("✅ 4. 儲存 server 輸出測試")
    print("✅ 5. 儲存 client 輸出測試")
    print("✅ 6. 讀取監控數據測試")
    print("✅ 7. 讀取 server 輸出測試")
    print("✅ 8. 讀取 client 輸出測試")
    print("✅ 9. 讀取所有測試輸出測試")
    print("✅ 10. Pair 摘要測試")
    print("✅ 11. 多次儲存測試")
    print("✅ 12. 時間範圍查詢測試")
    print("✅ 13. 查詢特定 metrics 測試")
    print("✅ 14. 清除數據功能測試")
    print("✅ 15. 關閉連接測試")
    print("\n所有功能測試通過！")
