import argparse
import paramiko
from ssh_executor import SSHExecutor
from dperfSetup import dperf
from config import Config
from APVSetup import APVSetup
from trafficGenerator import TrafficGenerator

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
        default='results/results.csv',
        help='指定輸出結果的檔案路徑,default為STDOUT'
    )
    
    parser.add_argument(
        '--log',
        type=str,
        default='./logs',
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
    args = parse_arguments()
    
    # 載入配置
    config = Config()
    config.from_yaml(args.config)
    apv=APVSetup(config)
    apv.connect()
    apv.setupEnv()

    # 建立 TrafficGenerator
    tg = TrafficGenerator(
        config=config,
        enable_redis=True
    )

    # 連接
    tg.connect()

    try:
        # 設定環境
        tg.setup_env()

        # 執行測試
        results = tg.run_test()

        print("\n" + "=" * 60)
        print("測試結果摘要:")
        print("=" * 60)

        for pair_name, pair_result in results.items():
            if pair_name == 'monitor_data':
                print(f"\n監控數據筆數: {len(pair_result)}")
            else:
                print(f"\n{pair_name}:")
                print(f"  Server: {pair_result.get('server')}")
                print(f"  Client: {pair_result.get('client')}")

    finally:
        # 斷開連接
        tg.disconnect()
        apv.clearEnv()
        apv.disconnect()


if __name__ == "__main__":
    main()
