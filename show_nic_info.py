#!/usr/bin/env python3
"""Display Traffic Generator NIC info: Name, Driver, PCI Address"""

from pathlib import Path

import paramiko
import yaml


def load_config() -> dict:
    """Load configuration file"""
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_remote_nic_info(ssh: paramiko.SSHClient) -> list[dict]:
    """Retrieve NIC information from the remote machine via SSH"""
    # Get all NIC names (exclude lo)
    cmd = "ls /sys/class/net | grep -v '^lo$'"
    _, stdout, _ = ssh.exec_command(cmd)
    nic_names = stdout.read().decode().strip().split("\n")

    nics = []
    for nic_name in sorted(nic_names):
        if not nic_name:
            continue

        info = {"name": nic_name, "driver": "N/A", "pci_address": "N/A"}

        # Get PCI address
        cmd = f"readlink /sys/class/net/{nic_name}/device 2>/dev/null"
        _, stdout, _ = ssh.exec_command(cmd)
        pci_link = stdout.read().decode().strip()
        if pci_link:
            info["pci_address"] = pci_link.split("/")[-1]

        # Get driver
        cmd = f"readlink /sys/class/net/{nic_name}/device/driver 2>/dev/null"
        _, stdout, _ = ssh.exec_command(cmd)
        driver_link = stdout.read().decode().strip()
        if driver_link:
            info["driver"] = driver_link.split("/")[-1]

        nics.append(info)

    return nics


def main():
    config = load_config()
    tg = config.get("test", {}).get("traffic_generator", {})

    host = tg.get("management_ip")
    port = tg.get("management_port", 22)
    username = tg.get("username")
    password = tg.get("password")

    print(f"\n{'='*60}")
    print(f"  Traffic Generator NIC Info ({host})")
    print(f"{'='*60}\n")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(host, port=port, username=username, password=password)

        print(f"{'Interface Name':<20} {'Driver':<15} {'PCI Address'}")
        print(f"{'-'*20} {'-'*15} {'-'*15}")

        nics = get_remote_nic_info(ssh)
        for nic in nics:
            print(f"{nic['name']:<20} {nic['driver']:<15} {nic['pci_address']}")

    except Exception as e:
        print(f"Connection failed: {e}")
    finally:
        ssh.close()

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
