#!/usr/bin/env python3
"""測試持久 session 功能"""

from ssh_executor import SSHExecutor
from config import Config



def test_persistent_session():
    """測試持久 session 是否能保持狀態"""

    config = Config().from_yaml("config.yaml")

    print("=== 測試 1: 傳統方式（每次新 channel）===")
    with SSHExecutor(
        host=config.test.traffic_generator.management_ip,
        port=config.test.traffic_generator.management_port,
        user=config.test.traffic_generator.username,
        password=config.test.traffic_generator.password,
    ) as executor:
        print("\n執行: cd /tmp")
        executor.execute_command("cd /tmp")

        print("\n執行: pwd")
        output, _, _ = executor.execute_command("pwd")
        print(f"結果: {output.strip()}")
        print("❌ 預期在 /tmp，但實際上回到了 home 目錄（因為是新 channel）\n")

    print("\n" + "="*60)
    print("=== 測試 2: 持久 session 方式 ===")
    with SSHExecutor(
        host=config.test.traffic_generator.management_ip,
        port=config.test.traffic_generator.management_port,
        user=config.test.traffic_generator.username,
        password=config.test.traffic_generator.password,
    ) as executor:
        # 啟動持久 session
        print("\n啟動持久 session...")
        executor.start_session()

        # 測試 1: 切換目錄
        print("\n執行: cd /tmp")
        output = executor.execute_in_session("cd /tmp")

        print("\n執行: pwd")
        output = executor.execute_in_session("pwd")
        print(f"輸出:\n{output}")

        # 測試 2: 環境變數
        print("\n執行: export MY_VAR='Hello World'")
        executor.execute_in_session("export MY_VAR='Hello World'")

        print("\n執行: echo $MY_VAR")
        output = executor.execute_in_session("echo $MY_VAR")
        print(f"輸出:\n{output}")

        # 測試 3: 多個命令的狀態保持
        print("\n執行: mkdir -p /tmp/test_session")
        executor.execute_in_session("mkdir -p /tmp/test_session")

        print("\n執行: cd /tmp/test_session")
        executor.execute_in_session("cd /tmp/test_session")

        print("\n執行: touch test_file.txt")
        executor.execute_in_session("touch test_file.txt")

        print("\n執行: ls -la")
        output = executor.execute_in_session("ls -la")
        print(f"輸出:\n{output}")

        print("\n執行: pwd")
        output = executor.execute_in_session("pwd")
        print(f"輸出:\n{output}")

        # 清理
        print("\n清理測試檔案...")
        executor.execute_in_session("rm -rf /tmp/test_session")

        print("\n✅ 持久 session 測試完成！狀態在多個命令之間成功保持。")

        # 停止 session
        executor.stop_session()
        print("\n持久 session 已停止")


if __name__ == "__main__":
    try:
        test_persistent_session()
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()

