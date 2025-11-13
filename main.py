import argparse
import paramiko
from ssh_executor import SSHExecutor
from config import Config

def load_yaml_config(yaml_path):
    """從 YAML 檔案載入配置"""
    return Config.from_yaml(yaml_path)

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
    parser.add_argument(
        '-c', '--config',
        type=str,
        default='config.yaml',
        help='指定 YAML 配置檔案路徑 (預設: config.yaml)'
    )
    
    args = parser.parse_args()

    # 讀取配置
    if args.config:
        # 從 YAML 載入配置
        config = load_yaml_config(args.config)
        print(f"已載入配置檔案: {args.config}")
        if args.verbose:
            print(f"  APV IP: {config.test.apv_management_ip}:{config.test.apv_managment_port}")
            print(f"  Traffic Generator IP: {config.test.traffic_generator.management_ip}:{config.test.traffic_generator.management_port}")
            print(f"  Client IP: {config.test.traffic_generator.pairs.client_ip}")
            print(f"  Server IP: {config.test.traffic_generator.pairs.server_ip}")
    else:
        # 使用預設配置
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
