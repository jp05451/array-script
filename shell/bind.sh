nmcli connection down enp182s0f0
nmcli connection down enp182s0f1
python3 /home/array/dpdk/usertools/dpdk-devbind.py -b vfio-pci 0000:b6:00.1 --noiommu-mode
python3 /home/array/dpdk/usertools/dpdk-devbind.py -b vfio-pci 0000:b6:00.0 --noiommu-mode
python3 /home/array/dpdk/usertools/dpdk-devbind.py --status
