python3 /home/array/dpdk/usertools/dpdk-devbind.py -b i40e 0000:b6:00.0
python3 /home/array/dpdk/usertools/dpdk-devbind.py -b i40e 0000:b6:00.1
nmcli connection up enp182s0f0
nmcli connection up enp182s0f1
python3 /home/array/dpdk/usertools/dpdk-devbind.py --status
