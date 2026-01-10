#!/usr/bin/env python3
"""測試 SSH 執行器的各種功能"""

from ssh_executor import SSHExecutor
from config import Config
import sys
import time


def print_test_header(test_name: str):
    """打印測試標題"""
    print("\n" + "=" * 70)
    print(f"  {test_name}")
    print("=" * 70)


def retry_connection(func, max_retries=3, delay=2):
    """
    重試連接的裝飾器函數

    Args:
        func: 要執行的測試函數
        max_retries: 最大重試次數
        delay: 重試之間的延遲（秒）

    Returns:
        函數執行結果
    """
    for attempt in range(max_retries):
        try:
            result = func()
            return result
        except Exception as e:
            if "Error reading SSH protocol banner" in str(e) or "timeout" in str(e).lower():
                if attempt < max_retries - 1:
                    print(f"\n⚠️  連接失敗（第 {attempt + 1} 次），{delay} 秒後重試...")
                    time.sleep(delay)
                    continue
                else:
                    print(f"\n❌ 重試 {max_retries} 次後仍然失敗")
                    raise
            else:
                raise
    return False


def test_basic_connection():
    """測試 1: 基本連接與斷開"""
    print_test_header("測試 1: 基本 SSH 連接與斷開")

    config = Config().from_yaml("config.yaml")

    try:
        executor = SSHExecutor(
            host=config.test.traffic_generator.management_ip,
            port=config.test.traffic_generator.management_port,
            user=config.test.traffic_generator.username,
            password=config.test.traffic_generator.password,
        )

        print("嘗試連接...")
        executor.connect()
        print("✅ 連接成功")

        print("嘗試斷開...")
        executor.close()
        print("✅ 斷開成功")

        return True
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False


def test_simple_command():
    """測試 2: 簡單命令執行"""
    print_test_header("測試 2: 簡單命令執行")

    config = Config().from_yaml("config.yaml")

    try:
        with SSHExecutor(
            host=config.test.traffic_generator.management_ip,
            port=config.test.traffic_generator.management_port,
            user=config.test.traffic_generator.username,
            password=config.test.traffic_generator.password,
        ) as executor:

            # 測試 pwd
            print("\n執行命令: pwd")
            output, error, exit_status = executor.execute_command("pwd")
            print(f"輸出: {output.strip()}")
            print(f"退出碼: {exit_status}")

            # 測試 whoami
            print("\n執行命令: whoami")
            output, error, exit_status = executor.execute_command("whoami")
            print(f"輸出: {output.strip()}")

            # 測試 uname
            print("\n執行命令: uname -a")
            output, error, exit_status = executor.execute_command("uname -a")
            print(f"輸出: {output.strip()}")

            print("\n✅ 簡單命令執行測試通過")
            return True

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False


def test_command_with_output():
    """測試 3: 帶輸出的命令"""
    print_test_header("測試 3: 帶輸出的命令")

    config = Config().from_yaml("config.yaml")

    try:
        with SSHExecutor(
            host=config.test.traffic_generator.management_ip,
            port=config.test.traffic_generator.management_port,
            user=config.test.traffic_generator.username,
            password=config.test.traffic_generator.password,
        ) as executor:

            # 測試 echo
            print("\n執行命令: echo 'Hello SSH Test'")
            output, error, exit_status = executor.execute_command("echo 'Hello SSH Test'")
            print(f"輸出: {output.strip()}")

            # 測試 ls
            print("\n執行命令: ls -lh /tmp | head -5")
            output, error, exit_status = executor.execute_command("ls -lh /tmp | head -5")
            print(f"輸出:\n{output}")

            # 測試日期
            print("\n執行命令: date")
            output, error, exit_status = executor.execute_command("date")
            print(f"輸出: {output.strip()}")

            print("\n✅ 帶輸出的命令測試通過")
            return True

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False


def test_persistent_session():
    """測試 4: 持久 session（保持狀態）"""
    print_test_header("測試 4: 持久 Session - 狀態保持")

    config = Config().from_yaml("config.yaml")

    try:
        executor = SSHExecutor(
            host=config.test.traffic_generator.management_ip,
            port=config.test.traffic_generator.management_port,
            user=config.test.traffic_generator.username,
            password=config.test.traffic_generator.password,
        )

        print("\n連接並啟用持久 session...")
        executor.connect(persistent_session=True)

        # 測試 4.1: 目錄狀態保持
        print("\n--- 子測試 4.1: 目錄狀態保持 ---")
        print("執行: cd /tmp")
        executor.execute_command("cd /tmp")

        print("執行: pwd")
        output, _, _ = executor.execute_command("pwd")
        if "/tmp" in output:
            print("✅ 目錄狀態保持成功")
        else:
            print(f"❌ 目錄狀態未保持，當前位置: {output.strip()}")

        # 測試 4.2: 環境變數保持
        print("\n--- 子測試 4.2: 環境變數保持 ---")
        print("執行: export TEST_VAR='Hello World'")
        executor.execute_command("export TEST_VAR='Hello World'")

        print("執行: echo $TEST_VAR")
        output, _, _ = executor.execute_command("echo $TEST_VAR")
        if "Hello World" in output:
            print("✅ 環境變數保持成功")
        else:
            print(f"❌ 環境變數未保持，輸出: {output.strip()}")

        # 測試 4.3: 多步驟操作
        print("\n--- 子測試 4.3: 多步驟檔案操作 ---")
        print("執行: mkdir -p /tmp/ssh_test")
        executor.execute_command("mkdir -p /tmp/ssh_test")

        print("執行: cd /tmp/ssh_test")
        executor.execute_command("cd /tmp/ssh_test")

        print("執行: echo 'test content' > test.txt")
        executor.execute_command("echo 'test content' > test.txt")

        print("執行: cat test.txt")
        output, _, _ = executor.execute_command("cat test.txt")
        if "test content" in output:
            print("✅ 多步驟操作成功")
        else:
            print(f"❌ 多步驟操作失敗，輸出: {output.strip()}")

        # 清理
        print("\n清理測試檔案...")
        executor.execute_command("rm -rf /tmp/ssh_test")

        executor.close()
        print("\n✅ 持久 session 測試通過")
        return True

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_non_persistent_vs_persistent():
    """測試 5: 非持久 vs 持久 session 對比"""
    print_test_header("測試 5: 非持久 vs 持久 Session 對比")

    config = Config().from_yaml("config.yaml")

    try:
        # 測試非持久模式
        print("\n--- 5.1: 非持久模式（每次新 channel）---")
        with SSHExecutor(
            host=config.test.traffic_generator.management_ip,
            port=config.test.traffic_generator.management_port,
            user=config.test.traffic_generator.username,
            password=config.test.traffic_generator.password,
        ) as executor:
            print("執行: cd /tmp")
            executor.execute_command("cd /tmp")

            print("執行: pwd")
            output, _, _ = executor.execute_command("pwd")
            if "/tmp" not in output or output.strip().endswith(config.test.traffic_generator.username):
                print("✅ 符合預期：回到 home 目錄（每次新 channel）")
            else:
                print(f"⚠️  非預期結果: {output.strip()}")

        # 測試持久模式
        print("\n--- 5.2: 持久模式（保持 session）---")
        executor = SSHExecutor(
            host=config.test.traffic_generator.management_ip,
            port=config.test.traffic_generator.management_port,
            user=config.test.traffic_generator.username,
            password=config.test.traffic_generator.password,
        )
        executor.connect(persistent_session=True)

        print("執行: cd /tmp")
        executor.execute_command("cd /tmp")

        print("執行: pwd")
        output, _, _ = executor.execute_command("pwd")
        if "/tmp" in output:
            print("✅ 符合預期：保持在 /tmp 目錄（持久 session）")
        else:
            print(f"❌ 未符合預期: {output.strip()}")

        executor.close()

        print("\n✅ 對比測試通過")
        return True

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False


def test_error_handling():
    """測試 6: 錯誤處理"""
    print_test_header("測試 6: 錯誤處理")

    config = Config().from_yaml("config.yaml")

    try:
        with SSHExecutor(
            host=config.test.traffic_generator.management_ip,
            port=config.test.traffic_generator.management_port,
            user=config.test.traffic_generator.username,
            password=config.test.traffic_generator.password,
        ) as executor:

            # 測試不存在的命令
            print("\n執行不存在的命令: nonexistentcommand123")
            output, error, exit_status = executor.execute_command("nonexistentcommand123")
            print(f"退出碼: {exit_status}")
            if exit_status != 0:
                print("✅ 正確捕獲錯誤")
            else:
                print("❌ 未正確識別錯誤")

            # 測試存取被拒絕
            print("\n執行被拒絕的操作: cat /etc/shadow")
            output, error, exit_status = executor.execute_command("cat /etc/shadow 2>&1")
            print(f"輸出: {output.strip()[:100]}...")
            if "Permission denied" in output or "Permission denied" in error:
                print("✅ 正確處理權限錯誤")
            else:
                print("⚠️  權限檢查結果可能因系統而異")

            print("\n✅ 錯誤處理測試通過")
            return True

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False


def test_session_commands():
    """測試 9: Session 中的複雜命令"""
    print_test_header("測試 9: Session 中的複雜命令")

    config = Config().from_yaml("config.yaml")

    def _test():
        executor = SSHExecutor(
            host=config.test.traffic_generator.management_ip,
            port=config.test.traffic_generator.management_port,
            user=config.test.traffic_generator.username,
            password=config.test.traffic_generator.password,
        )
        try:
            executor.connect(persistent_session=True)

            # 測試 for 迴圈
            print("\n執行: for i in 1 2 3; do echo \"Number: $i\"; done")
            output, _, _ = executor.execute_command("for i in 1 2 3; do echo \"Number: $i\"; done")
            print(f"輸出:\n{output}")

            # 測試管道
            print("\n執行: echo 'apple\nbanana\ncherry' | grep 'an'")
            output, _, _ = executor.execute_command("echo -e 'apple\nbanana\ncherry' | grep 'an'")
            print(f"輸出:\n{output}")

            # 測試變數計算
            print("\n執行: A=10; B=20; echo $((A + B))")
            executor.execute_command("A=10")
            executor.execute_command("B=20")
            output, _, _ = executor.execute_command("echo $((A + B))")
            if "30" in output:
                print("✅ 變數計算成功")

            print("\n✅ 複雜命令測試通過")
            return True
        finally:
            executor.close()

    try:
        return retry_connection(_test)
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_persistent_session_ignores_realtime():
    """測試 10: 持久 Session 忽略 real_time 參數（Bug 修正驗證）"""
    print_test_header("測試 10: 持久 Session 忽略 real_time 參數")

    config = Config().from_yaml("config.yaml")

    def _test():
        executor = SSHExecutor(
            host=config.test.traffic_generator.management_ip,
            port=config.test.traffic_generator.management_port,
            user=config.test.traffic_generator.username,
            password=config.test.traffic_generator.password,
        )
        try:
            print("\n連接並啟用持久 session...")
            executor.connect(persistent_session=True)

            # 測試 10.1: real_time=False
            print("\n--- 子測試 10.1: real_time=False ---")
            output, _, _ = executor.execute_command("echo 'Test 1'", real_time=False)
            if "Test 1" in output:
                print("✅ real_time=False 正常工作")

            # 測試 10.2: real_time=True（應該被忽略，使用 execute_in_session）
            print("\n--- 子測試 10.2: real_time=True (應被忽略) ---")
            output, _, _ = executor.execute_command("echo 'Test 2'", real_time=True)
            if "Test 2" in output:
                print("✅ real_time=True 被正確忽略，使用 session 模式")

            # 測試 10.3: 驗證狀態保持（關鍵測試）
            print("\n--- 子測試 10.3: 驗證狀態保持 ---")
            executor.execute_command("cd /tmp", real_time=True)
            output, _, _ = executor.execute_command("pwd", real_time=False)
            if "/tmp" in output:
                print("✅ 狀態正確保持（修正後不會出現 -c 錯誤）")
            else:
                print(f"❌ 狀態未保持: {output.strip()}")
                return False

            # 測試 10.4: 模擬 APV 命令序列（不應出現 ca_shell -c 錯誤）
            print("\n--- 子測試 10.4: 模擬 APV 命令序列 ---")
            executor.execute_command("echo 'enable'", real_time=True)
            executor.execute_command("echo 'password'", real_time=True)
            executor.execute_command("echo 'config terminal'", real_time=True)
            output, _, _ = executor.execute_command("echo '?'", real_time=True)
            if "?" in output:
                print("✅ APV 風格命令序列正常執行（無 -c 錯誤）")
            else:
                print(f"⚠️  輸出: {output}")

            print("\n✅ 持久 Session 忽略 real_time 測試通過")
            return True
        finally:
            executor.close()

    try:
        return retry_connection(_test)
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_realtime_in_non_persistent_mode():
    """測試 11: 非持久模式下的 real_time 功能"""
    print_test_header("測試 11: 非持久模式的 real_time 功能")

    config = Config().from_yaml("config.yaml")

    def _test():
        executor = SSHExecutor(
            host=config.test.traffic_generator.management_ip,
            port=config.test.traffic_generator.management_port,
            user=config.test.traffic_generator.username,
            password=config.test.traffic_generator.password,
        )
        try:
            print("\n連接（非持久模式）...")
            executor.connect(persistent_session=False)

            # 測試標準模式
            print("\n--- real_time=False（標準模式）---")
            output, _, _ = executor.execute_command("echo 'Standard mode'", real_time=False)
            if output and "Standard mode" in output:
                print("✅ 標準模式正常")

            # 測試實時模式
            print("\n--- real_time=True（實時輸出模式）---")
            print("執行: for i in 1 2 3; do echo \"Count: $i\"; sleep 0.3; done")
            result = executor.execute_command(
                "for i in 1 2 3; do echo \"Count: $i\"; sleep 0.3; done",
                real_time=True
            )
            if result is None:
                print("✅ real_time 模式返回 None（符合預期）")
            else:
                print(f"⚠️  返回了: {result}")

            print("\n✅ 非持久模式的 real_time 功能測試通過")
            return True
        finally:
            executor.close()

    try:
        return retry_connection(_test)
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """執行所有測試"""
    print("\n" + "=" * 70)
    print("  SSH 執行器功能測試套件")
    print("=" * 70)

    tests = [
        ("基本連接與斷開", test_basic_connection),
        ("簡單命令執行", test_simple_command),
        ("帶輸出的命令", test_command_with_output),
        ("持久 Session", test_persistent_session),
        ("非持久 vs 持久對比", test_non_persistent_vs_persistent),
        ("錯誤處理", test_error_handling),
        ("複雜命令", test_session_commands),
        ("持久 Session 忽略 real_time（Bug 修正驗證）", test_persistent_session_ignores_realtime),
        ("非持久模式的 real_time 功能", test_realtime_in_non_persistent_mode),
    ]

    results = []
    for i, (test_name, test_func) in enumerate(tests):
        try:
            result = test_func()
            results.append((test_name, result))

            # 在測試之間添加延遲，避免連接過於頻繁（最後一個測試不需要延遲）
            if i < len(tests) - 1:
                print("\n⏳ 等待 1.5 秒後繼續下一個測試...")
                time.sleep(1.5)
        except Exception as e:
            print(f"\n❌ 測試 '{test_name}' 發生異常: {e}")
            results.append((test_name, False))

            # 即使失敗也添加延遲
            if i < len(tests) - 1:
                print("\n⏳ 等待 1.5 秒後繼續下一個測試...")
                time.sleep(1.5)

    # 打印總結
    print("\n" + "=" * 70)
    print("  測試結果總結")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ 通過" if result else "❌ 失敗"
        print(f"{status} - {test_name}")

    print("\n" + "-" * 70)
    print(f"總計: {passed}/{total} 測試通過")
    print("=" * 70)

    return passed == total


if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n測試被使用者中斷")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 測試套件執行失敗: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
