import argparse
import paramiko
from ssh_executor import SSHExecutor
from dperfSetup import dperf
from config import Config
from APVSetup import APVSetup
from trafficGenerator import TrafficGenerator

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
        '-s','--script',
        type=str,
        default='shell.sh',
        help='Path to the shell script to execute (default: shell.sh)'
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
        '-p','--packet_size'
        ,type=int,
        help='Packet size in bytes'
    )
    parser.add_argument(
        '--sessions',
        type=int,
        help='Number of simultaneous connections'
    )
    parser.add_argument(
        '-i','--packet_interval',
        type=int,
        help='Packet interval in microseconds'
    )
    
    parser.add_argument(
        '-o','--output',
        type=str,
        default='results/results.csv',
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
        
    if args.sessions is not None:
        config.test.pairs.client.cc = args.sessions
        
    # Packet size
    if args.packet_size is not None:
        config.test.traffic_generator.pairs.payload_size = args.packet_size
        
    # Packet interval
    if args.packet_interval is not None:
        config.test.pairs.server.keepalive = args.packet_interval
        config.test.pairs.client.keepalive = args.packet_interval



def main():
    args = parse_arguments()
    
    # Load configuration
    config = Config()
    config.from_yaml(args.config)
    argOverrideConfig(args, config)
    dry_run = args.dry_run
    apv=APVSetup(config)
    apv.connect()
    apv.clearEnv()
    apv.setupEnv(dry_run=dry_run)
    apv.disconnect()

    # Create TrafficGenerator
    tg = TrafficGenerator(
        config=config,
        enable_redis=args.enable_redis
    )

    # Connect
    tg.connect()

    try:
        # Setup environment
        tg.setup_env()

        # Run test
        results = tg.run_test(parallel=True, enable_monitor=True, dry_run=dry_run)

        print("\n" + "=" * 60)
        print("Test Summary:")
        print("=" * 60)

        for pair_name, pair_result in results.items():
            if pair_name == 'monitor_data':
                print(f"\nMonitoring data points: {len(pair_result)}")
            else:
                print(f"\n{pair_name}:")
                print(f"  Server: {pair_result.get('server')}")
                print(f"  Client: {pair_result.get('client')}")

    finally:
        # Disconnect
        tg.clearEnv()
        tg.disconnect()
        apv.connect()
        apv.clearEnv(dry_run=dry_run)
        apv.disconnect()


if __name__ == "__main__":
    main()
