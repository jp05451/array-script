$ git clone https://github.com/DPDK/dpdk
# 一次安裝所有需要的套件
sudo dnf install -y \
    epel-release \
    python3 \
    python3-pip \
    python3-pyelftools \
    numactl-devel \
    libpcap-devel \
    openssl-devel \
    libbsd-devel \
    kernel-devel \
    kernel-headers \
    elfutils-libelf-devel \
    zlib-devel \
    jansson-devel \
    gcc \
    gcc-c++ \
    make \
    git

# 啟用 CRB 儲存庫（包含部分開發套件）
sudo dnf config-manager --set-enabled crb
sudo dnf makecache

# 安裝 Meson 和 Ninja（建置工具）
sudo pip3 install meson ninja
meson setup build
cd build
ninja
sudo meson install
sudo ldconfig