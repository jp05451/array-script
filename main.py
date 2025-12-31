import argparse
import paramiko
from ssh_executor import SSHExecutor
from dperfSetup import dperf
from config import Config

def load_yaml_config(yaml_path):
    """從 YAML 檔案載入配置"""
    return Config.from_yaml(yaml_path)

def parse_arguments():
    """解析命令列參數"""
    parser = argparse.ArgumentParser(
        description='透過 SSH 連接到遠端機器並執行指定的 shell 腳本'
    )
    parser.add_argument(
        '-s','--script',
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
        help='指定 YAML 配置檔案路徑 (預設: config.yaml) 如果輸入其他參數，則會覆蓋 YAML 配置中的對應值'
    )
    parser.add_argument(
        '-d','--duration'
        ,type=int,
        help='指定測試持續時間,單位為秒'
    )
    parser.add_argument(
        '-p','--packet_size'
        ,type=int,
        help='指定封包大小,單位為bytes'
    )
    parser.add_argument(
        '--sessions',
        type=int,
        help='指定同時啟動的連線數量'
    )
    parser.add_argument(
        '-i','--packet_interval',
        type=int,
        help='指定封包間隔時間,單位為微秒'
    )
    
    parser.add_argument(
        '-o','--output',
        type=str,
        default='resaults.csv',
        help='指定輸出結果的檔案路徑,default為STDOUT'
    )
    
    parser.add_argument(
        '--log',
        type=str,
        default='./log',
        help='指定日誌檔案資料夾 (預設: ./log)'
    )
    return parser.parse_args()

def argOverrideConfig(args, config):
    """使用命令列參數覆蓋配置"""
    # 覆蓋配置中的對應值
    
    # 傳輸時長
    if args.duration is not None:
        config.test.pairs.client.duration = args.duration
        config.test.pairs.server.duration = args.duration
        
    if args.sessions is not None:
        config.test.pairs.client.cc = args.sessions
        
    # 封包大小
    if args.packet_size is not None:
        config.test.traffic_generator.pairs.payload_size = args.packet_size
        
    # 封包間隔時間
    if args.packet_interval is not None:
        config.test.pairs.server.keepalive = args.packet_interval
        config.test.pairs.client.keepalive = args.packet_interval

def main():
    """主程式"""
    args = parse_arguments()

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
        exit("錯誤：未指定配置檔案")

    # 處理輸出路徑參數
    # log_path = None if args.log == 'STDOUT' else args.log
    avx = dperf(config,pair_index=0, log_path=args.log, output_path=args.output)
    avx.setupEnv()

    # 建立兩個執行緒分別連線到 server 和 client
    try:
        avx.runPairTest()
        print("=== Server 和 Client 執行緒已完成 ===\n")

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


if __name__ == "__main__":
    main()
