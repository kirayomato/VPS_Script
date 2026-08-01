#!/bin/bash
#================================================
# 简易 VPS 性能测试脚本 (含多核倍率)
# 仅使用 Ubuntu 自带软件
# 同时输出到控制台 + 文件 (tee 方案)
#================================================

# 结果文件
REPORT="vps_test_$(date '+%Y%m%d_%H%M%S').log"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

line() { echo -e "${CYAN}------------------------------------------------${NC}"; }
title() {
    line
    echo -e "${GREEN} $1 ${NC}"
    line
}

#================================================
# 1. 系统信息
#================================================
show_sysinfo() {
    title "系统信息"
    echo "主机名   : $(hostname)"
    echo "系统版本 : $(lsb_release -d 2>/dev/null | cut -f2 || grep PRETTY_NAME /etc/os-release | cut -d'"' -f2)"
    echo "内核版本 : $(uname -r)"
    echo "CPU型号  : $(grep 'model name' /proc/cpuinfo | head -1 | cut -d':' -f2 | sed 's/^ *//')"
    echo "CPU核心  : $(nproc) 核"
    echo "内存总量 : $(free -h | awk '/Mem:/ {print $2}')"
    echo "磁盘总量 : $(df -h / | awk 'NR==2 {print $2}')"
    echo "运行时间 : $(uptime -p 2>/dev/null || uptime)"
    echo ""
}

#================================================
# 2. CPU 性能测试 (含多核倍率)
#================================================
test_cpu() {
    title "CPU 性能测试"
    CORES=$(nproc)

    echo -e "${YELLOW}[基准] OpenSSL AES-256-CBC 加密速度${NC}"
    openssl speed -elapsed -evp aes-256-cbc 2>/dev/null | grep '^aes-256' | tail -1
    echo ""

    # 单核测试
    echo -e "${YELLOW}[单核测试] 单个核心计算 SHA256 (512MB)${NC}"
    start=$(date +%s.%N)
    dd if=/dev/zero bs=1M count=512 2>/dev/null | sha256sum >/dev/null
    end=$(date +%s.%N)
    single_time=$(echo "$end - $start" | bc)
    echo "单核耗时 : ${single_time} 秒"
    echo ""

    # 多核测试
    echo -e "${YELLOW}[多核测试] $CORES 个核心并行 (每核 512MB)${NC}"
    start=$(date +%s.%N)
    for i in $(seq 1 $CORES); do
        ( dd if=/dev/zero bs=1M count=512 2>/dev/null | sha256sum >/dev/null ) &
    done
    wait
    end=$(date +%s.%N)
    multi_time=$(echo "$end - $start" | bc)
    echo "多核耗时 : ${multi_time} 秒 (共完成 $((CORES * 512))MB)"
    echo ""

    # 计算倍率
    echo -e "${YELLOW}[多核倍率] 并行加速比${NC}"
    if command -v bc &>/dev/null && [ -n "$single_time" ]; then
        theory_single=$(echo "$single_time * $CORES" | bc)
        ratio=$(echo "scale=2; $theory_single / $multi_time" | bc)
        efficiency=$(echo "scale=1; $ratio / $CORES * 100" | bc)
        echo "核心数量     : ${CORES}"
        echo "单核基准时间 : ${single_time} 秒"
        echo "多核实际时间 : ${multi_time} 秒"
        echo -e "${GREEN}多核倍率     : ${ratio}x  (理论最大 ${CORES}x)${NC}"
        echo -e "${GREEN}并行效率     : ${efficiency}%${NC}"
    else
        echo "无法计算 (请安装 bc: sudo apt install bc)"
    fi
    echo ""
}

#================================================
# 3. 磁盘 I/O 性能测试
#================================================
test_disk() {
    title "磁盘 I/O 性能测试"
    TMPFILE="./disk_test_tmp"

    echo -e "${YELLOW}[写入测试] 顺序写入 1GB${NC}"
    dd if=/dev/zero of=$TMPFILE bs=1M count=1024 oflag=direct 2>&1 | tail -1
    echo ""

    sync; echo 3 > /proc/sys/vm/drop_caches 2>/dev/null

    echo -e "${YELLOW}[读取测试] 顺序读取 1GB${NC}"
    dd if=$TMPFILE of=/dev/null bs=1M iflag=direct 2>&1 | tail -1
    echo ""

    echo -e "${YELLOW}[随机写测试] 4K 小块写入${NC}"
    dd if=/dev/zero of=$TMPFILE bs=4k count=10000 oflag=direct 2>&1 | tail -1
    echo ""

    rm -f $TMPFILE
}

#================================================
# 4. 网络性能测试
#================================================
test_network() {
    title "网络性能测试"

    echo -e "${YELLOW}[延迟测试] Ping 主要节点${NC}"
    for host in "阿里云:223.5.5.5" "谷歌:8.8.8.8" "Cloudflare:1.1.1.1"; do
        name=$(echo $host | cut -d':' -f1)
        ip=$(echo $host | cut -d':' -f2)
        result=$(ping -c 4 -W 2 $ip 2>/dev/null | tail -1 | awk -F '/' '{print $5}')
        if [ -n "$result" ]; then
            echo "$name ($ip) : 平均延迟 ${result} ms"
        else
            echo "$name ($ip) : 超时/不可达"
        fi
    done
    echo ""

    echo -e "${YELLOW}[下载测试] Cloudflare 100MB${NC}"
    wget -O /dev/null "https://speed.cloudflare.com/__down?bytes=104857600" 2>&1 \
        | grep -o '[0-9.]\+ [KM]B/s' | tail -1 | awk '{print "下载速度: " $0}'
    echo ""

    echo -e "${YELLOW}[IP信息]${NC}"
    echo "公网IP: $(wget -qO- --timeout=5 https://api.ipify.org 2>/dev/null || echo '获取失败')"
    echo ""
}

#================================================
# 主逻辑 (所有输出走这里)
#================================================
run_all() {
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}         VPS 简易性能测试报告${NC}"
    echo -e "${GREEN}         $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo -e "${GREEN}================================================${NC}"
    echo ""

    show_sysinfo
    test_cpu
    test_disk
    # test_network

    title "测试完成"
    echo -e "${GREEN}所有测试已完成！${NC}"
}

#================================================
# 入口: 用 tee 同时输出到控制台和文件
#================================================
clear

if ! command -v bc &>/dev/null; then
    echo -e "${YELLOW}警告: 未安装 bc, 无法计算倍率, 请运行: sudo apt install -y bc${NC}"
    echo ""
fi

# 关键: 2>&1 合并错误输出, tee 分流到屏幕和文件
run_all 2>&1 | tee >(sed 's/\x1b\[[0-9;]*m//g' > "$REPORT")

echo -e "${CYAN}>>> 结果已保存到文件: ${YELLOW}${REPORT}${NC}"