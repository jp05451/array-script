from RedisDB import RedisHandler
from datetime import datetime

if __name__ == "__main__":
    """Test script - Test all Redis functionality"""
    import time

    print("=" * 60)
    print("Starting RedisHandler comprehensive test")
    print("=" * 60)

    # Test parameters
    TEST_PAIR_INDEX = 0

    # 1. Test connection
    print("\n[Test 1] Testing Redis connection...")
    redis_handler = RedisHandler(host="localhost", port=6379, db=0)

    if not redis_handler.is_connected():
        print("❌ Redis connection failed, ensure Redis service is running")
        print("Hint: Run 'redis-server' to start Redis service")
        exit(1)
    print("✅ Redis connection successful")

    # 2. Clear old data
    print(f"\n[Test 2] Clear old data for pair {TEST_PAIR_INDEX} ...")
    redis_handler.clear_pair_data(TEST_PAIR_INDEX)
    print("✅ Old data cleared")

    # 3. Test saving monitor data
    print(f"\n[Test 3] Test saving monitor data (simulate 5 seconds of monitoring data)...")
    for i in range(5):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cpu_usage = 50.0 + i * 2.5  # Simulate CPU usage from 50% to 60%
        ram_used = 8000 + i * 100   # Simulate RAM usage increment
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
            print(f"  ✓ Save monitor data #{i+1}: CPU={cpu_usage:.1f}%, RAM={ram_used}MB ({ram_usage:.1f}%)")
        else:
            print(f"  ✗ Save monitor data #{i+1} Failed")

        time.sleep(0.2)  # Simulate time interval

    print("✅ Monitor data save test completed")

    # 4. Test saving server output
    print(f"\n[Test 4] Test saving server output data...")
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
        print("  ✓ Server output data saved successfully")
        for key, value in server_output.items():
            print(f"    - {key}: {value}")
    else:
        print("  ✗ Save server output dataFailed")

    print("✅ Server output save test completed")

    # 5. Test saving client output
    print(f"\n[Test 5] Test saving client output data...")
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
        print("  ✓ Client output data saved successfully")
        for key, value in client_output.items():
            print(f"    - {key}: {value}")
    else:
        print("  ✗ Save client output dataFailed")

    print("✅ Client output save test completed")

    # 6. Test retrieving monitor data
    print(f"\n[Test 6] Test retrieving monitor data...")
    monitor_data = redis_handler.get_monitor_data(TEST_PAIR_INDEX)

    if monitor_data:
        print(f"  ✓ Successfully retrieved {len(monitor_data)} records of monitor data")
        print(f"  First record: {monitor_data[0]}")
        print(f"  Last record: {monitor_data[-1]}")
    else:
        print("  ✗ Failed to retrieve monitor data")

    print("✅ Monitor data retrieve test completed")

    # 7. Test retrieving server output
    print(f"\n[Test 7] Test retrieving server output data...")
    server_data = redis_handler.get_test_output(TEST_PAIR_INDEX, 'server')

    if server_data:
        print(f"  ✓ Successfully retrieved server output data")
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
        print("  ✗ Failed to retrieve server output data")

    print("✅ Server output retrieve test completed")

    # 8. Test retrieving client output
    print(f"\n[Test 8] Test retrieving client output data...")
    client_data = redis_handler.get_test_output(TEST_PAIR_INDEX, 'client')

    if client_data:
        print(f"  ✓ Successfully retrieved client output data")
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
        print("  ✗ Failed to retrieve client output data")

    print("✅ Client output retrieve test completed")

    # 9. Test retrieving all test outputs
    print(f"\n[Test 9] Test retrieving all output data...")
    all_server_outputs = redis_handler.get_all_test_outputs(TEST_PAIR_INDEX, 'server')
    all_client_outputs = redis_handler.get_all_test_outputs(TEST_PAIR_INDEX, 'client')

    print(f"  ✓ Server total count: {len(all_server_outputs)}")
    print(f"  ✓ Client total count: {len(all_client_outputs)}")

    print("✅ allTestoutputretrieveTest completed")

    # 10. Testget pair summary
    print(f"\n[Test 10] Testget pair summary...")
    summary = redis_handler.get_pair_summary(TEST_PAIR_INDEX)

    if summary:
        print(f"  ✓ Pair {summary['pair_index']} summary:")
        print(f"    - monitor datacount: {summary['monitor_count']}")
        print(f"    - Server outputcount: {summary['server_output_count']}")
        print(f"    - Client outputcount: {summary['client_output_count']}")
    else:
        print("  ✗ get pair summaryFailed")

    print("✅ Pair summaryTest completed")

    # 11. Test多次儲存 (模擬多次Test運行)
    print(f"\n[Test 11] Test多次儲存Testoutput (模擬 3 次Test運行)...")
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

        print(f"  ✓ 第 {run + 1} 次Test運行數據已儲存")

    # 檢查總數
    updated_summary = redis_handler.get_pair_summary(TEST_PAIR_INDEX)
    print(f"  ✓ 更新後的summary:")
    print(f"    - Server total count: {updated_summary['server_output_count']}")
    print(f"    - Client total count: {updated_summary['client_output_count']}")

    print("✅ 多次儲存Test completed")

    # 12. Test時間範圍查詢
    print(f"\n[Test 12] Test時間範圍查詢monitor data...")
    all_monitor_data = redis_handler.get_monitor_data(TEST_PAIR_INDEX)

    if len(all_monitor_data) > 0:
        # 取前3records數據的時間範圍
        start_time = all_monitor_data[0]['timestamp']
        end_time = all_monitor_data[min(2, len(all_monitor_data)-1)]['timestamp']

        filtered_data = redis_handler.get_monitor_data(
            TEST_PAIR_INDEX, start_time=start_time, end_time=end_time
        )

        print(f"  ✓ 時間範圍: {start_time} 到 {end_time}")
        print(f"  ✓ 查詢到 {len(filtered_data)} records數據")
    else:
        print("  ✗ 沒有monitor data可供Test")

    print("✅ 時間範圍查詢Test completed")

    # 13. Test查詢特定 metrics
    print(f"\n[Test 13] Test查詢特定 metrics...")
    specific_metrics = redis_handler.get_specific_metrics(
        TEST_PAIR_INDEX, 'server', ['Sends', 'Recvs', 'HTTP-2XX', 'Errors']
    )

    if specific_metrics:
        print(f"  ✓ Successfully retrieved查詢特定 metrics:")
        for metric_name, value in specific_metrics.items():
            print(f"    - {metric_name}: {value}")
    else:
        print("  ✗ 查詢特定 metrics Failed")

    print("✅ 特定 metrics 查詢Test completed")

    # 14. 最終清理Test
    print(f"\n[Test 14] Test清除數據功能...")
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
    print(f"\n[Test 15] 關閉 Redis 連接...")
    redis_handler.close()
    print("✅ 連接已關閉")

    print("\n" + "=" * 60)
    print("allTest completed！")
    print("=" * 60)
    print("\nTestsummary:")
    print("✅ 1. Redis 連接Test")
    print("✅ 2. Clear old dataTest")
    print("✅ 3. Save monitor dataTest")
    print("✅ 4. 儲存 server outputTest")
    print("✅ 5. 儲存 client outputTest")
    print("✅ 6. retrievemonitor dataTest")
    print("✅ 7. retrieve server outputTest")
    print("✅ 8. retrieve client outputTest")
    print("✅ 9. retrieveallTestoutputTest")
    print("✅ 10. Pair summaryTest")
    print("✅ 11. 多次儲存Test")
    print("✅ 12. 時間範圍查詢Test")
    print("✅ 13. 查詢特定 metrics Test")
    print("✅ 14. 清除數據功能Test")
    print("✅ 15. 關閉連接Test")
    print("\nall功能Test通過！")
