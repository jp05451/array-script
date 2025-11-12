import argparse
from ssh_executor import SSHExecutor
from config import Config


def main():
    """主程式"""
    parser = argparse.ArgumentParser(
        description='透過 SSH 連接到遠端機器並執行指定的 shell 腳本'
    )
    parser.add_argument(
        '-s', '--script',
        type=str,
        default='shell.sh',
        help='要執行的 shell 腳本路徑 (預設: shell.sh)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='顯示詳細資訊'
    )
    parser.add_argument(
        '-r', '--realtime',
        action='store_true',
        help='即時輸出執行結果'
    )

    args = parser.parse_args()

    # 讀取配置
    config = Config()

    # 建立 SSH 執行器
    executor = SSHExecutor(config)

    try:
        # 連接到遠端主機
        executor.connect()

        # 執行腳本
        executor.execute_script(args.script, real_time=args.realtime)

    except FileNotFoundError:
        print(f"錯誤：找不到腳本文件 '{args.script}'")
    except KeyboardInterrupt:
        print("\n\n程式已被使用者中斷")
    except paramiko.AuthenticationException:
        print("錯誤：身份驗證失敗，請檢查用戶名和密碼")
    except paramiko.SSHException as e:
        print(f"SSH 錯誤：{e}")
    except Exception as e:
        print(f"發生錯誤：{e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
    finally:
        # 關閉連接
        executor.close()


if __name__ == "__main__":
    main()
