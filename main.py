import argparse
from config import Config
from APVSetup import APVSetup
from trafficGenerator import TrafficGenerator
from time import sleep

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Connect to remote machines via SSH and execute specified shell scripts'
    )
    parser.add_argument(
        "--enable-redis",
        action='store_true',
        default=False,
        help="Whether to enable Redis storage (default: False)"
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Display detailed information'
    )
    parser.add_argument(
        '-r', '--realtime',
        action='store_true',
        help='Real-time output of execution results'
    )
    parser.add_argument(
        '-c', '--config',
        type=str,
        default='config.yaml',
        help='Path to the YAML configuration file (default: config.yaml). Other arguments will override values in the YAML file'
    )
    parser.add_argument(
        '-d','--duration'
        ,type=str,
        help='Total test duration (supported formats: s=seconds, m=minutes, h=hours, e.g., 40s, 2m, 1h)'
    )
    parser.add_argument(
        '-p','--packet-size'
        ,type=int,
        help='Packet size in bytes e.g., 1024'
    )
    parser.add_argument(
        '--sessions',
        type=str,
        help='Number of simultaneous connections e.g., 2k'
    )
    parser.add_argument(
        '--packet-interval',
        type=str,
        help='Packet interval in microseconds e.g., 1000us'
    )
    
    parser.add_argument(
        '-o','--output',
        type=str,
        default='results',
        help='Path to the results file (default results/results.csv)'
    )
    
    parser.add_argument(
        '--log',
        type=str,
        default='./logs',
        help='Logs directory (default: ./logs)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=False,
        help='Dry run mode: execute all setup/teardown steps but skip actual dperf traffic generation'
    )
    return parser.parse_args()

def argOverrideConfig(args, config):
    """Override configuration with command line arguments"""
    # Override configuration values
    # Duration
    if args.duration is not None:
        config.test.traffic_generator.duration = args.duration
    
    if args.sessions is not None or args.packet_size is not None or args.packet_interval is not None:
        for pair in config.test.traffic_generator.pairs:
            
            # Sessions
            if args.sessions is not None:
                pair.client.cc = args.sessions
                
            # Packet size
            if args.packet_size is not None:
                pair.payload_size = args.packet_size
                
            # Packet interval
            if args.packet_interval is not None:
                pair.server.keepalive = args.packet_interval
                pair.client.keepalive = args.packet_interval


def main():
    args = parse_arguments()
    
    # Load configuration
    config = Config()
    config.from_yaml(args.config)

    argOverrideConfig(args, config)
    
    print(f"config args {config.to_dict()}")

    dryRun=args.dry_run
    print(f"Dry run mode: {dryRun}")

    apv=APVSetup(config,log_path=args.log)
    if not dryRun:
        apv.connect()
        apv.clearEnv()
        apv.setupEnv(dry_run=dryRun)
        apv.resolvePortNames()
        apv.disconnect()

    # Create TrafficGenerator
    tg = TrafficGenerator(
        config=config,
        enable_redis=args.enable_redis,
        log_path=args.log,
        output_path=args.output
    )

    if not dryRun:
        tg.connect()

    try:
        # Setup environment
        tg.setup_env(dry_run=dryRun)

        # Run test
        tg.run_test(parallel=True, enable_monitor=True, dry_run=dryRun)


    finally:
        if not dryRun:
            tg.clearEnv()
            tg.disconnect()

            apv.connect()
            try:
                apv.collectAndProcessSLBStats(args.output)
                tg.appendSLBStats(apv.per_pair_slb)
            except Exception as e:
                print(f"[APVSetup] 收集 SLB 統計資料失敗: {e}")
            apv.clearEnv()
            apv.disconnect()
            print("================================================================")
            tg.printFormattedSummary(apv.per_pair_slb)

if __name__ == "__main__":
    main()
