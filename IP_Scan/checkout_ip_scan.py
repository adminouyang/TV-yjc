#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP 扫描与有效性检测脚本（高性能异步版）
======================================
优化手段：
  方案一：asyncio + aiohttp 替换线程池 + requests（协程并发，复用连接池）
  方案二：先 TCP 预检（0.4s 超时）过滤不可达 IP，再对通过的 IP 发 HTTP 确认
功能：读取 IP_Scan/checkout_ip/*_config.txt，扫描有效 ip:port 并保存
"""
import asyncio
import os
import time
import glob
import socket
import errno

import aiohttp
from aiohttp import ClientTimeout, TCPConnector


# ============ 配置区 ============
BASE_DIR = "IP_Scan/checkout_ip"
SAVE_DIR = "IP_Scan/checkout_ip"          # 有效 ip 保存目录（*_ip.txt）

TCP_TIMEOUT = 0.4        # TCP 预检超时（秒）
HTTP_TIMEOUT = 2.0       # HTTP 确认总超时（秒）
TCP_CONCURRENCY = 800    # TCP 预检并发数
HTTP_CONCURRENCY = 600   # HTTP 确认并发数


# ============ 配置解析（保持不变） ============
def read_config(config_file):
    """读取配置文件，返回 [(ip_part, port, option), ...]"""
    print(f"读取设置文件：{config_file}")
    ip_configs = []
    try:
        with open(config_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if "," in line and not line.startswith("#"):
                    parts = line.split(',')
                    ip_part, port = parts[0].strip().split(':')
                    opt_raw = parts[1].strip() if len(parts) > 1 else ""
                    option = int(opt_raw) if opt_raw else None
                    port = port.strip()
                    ip_configs.append((ip_part, port, option))
                    url_end = "/status" if option is not None and option >= 10 else "/stat"
                    print(f"第{line_num}行：{ip_part}:{port} option={option} 添加到扫描列表 (检测路径{url_end})")
        return ip_configs
    except Exception as e:
        print(f"读取文件错误: {e}")
        return []


def generate_ip_ports_d_only(ip, port, c_str, d):
    """仅扫描 d 部分（1-255），c 固定"""
    c = int(c_str)
    return [f"{ip}.{c}.{d_val}:{port}" for d_val in range(1, 256)]


def generate_ip_ports_cd(ip, port, c_first, c_last):
    """同时扫描 c 部分 [c_first, c_last) 与 d 部分 (1-255)"""
    return [f"{ip}.{c}.{d}:{port}" for c in range(c_first, c_last) for d in range(1, 256)]


# ============ 异步核心：TCP 预检 + HTTP 确认 ============
async def tcp_probe(sem, ip_port):
    """TCP 预检：尝试建立 TCP 连接，成功返回 ip_port，失败返回 None"""
    host, port_str = ip_port.rsplit(':', 1)
    port = int(port_str)
    try:
        async with sem:
            loop = asyncio.get_running_loop()
            # getaddrinfo 解析 + TCP 连接，统一用 wait_for 限时
            infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            sock = None
            for family, stype, proto, canonname, sockaddr in infos:
                try:
                    sock = socket.socket(family, stype, proto)
                    sock.setblocking(False)
                    await asyncio.wait_for(
                        loop.sock_connect(sock, sockaddr),
                        timeout=TCP_TIMEOUT,
                    )
                    return ip_port
                except Exception:
                    continue
                finally:
                    if sock is not None:
                        try:
                            sock.close()
                        except Exception:
                            pass
    except Exception:
        return None
    return None


async def http_check(session, sem, ip_port, url_end):
    """HTTP 确认：响应含 udpxy 特征关键字则返回 ip_port"""
    url = f"http://{ip_port}{url_end}"
    try:
        async with sem:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                # 只读前 1024 字节判断，避免大响应占用带宽
                body = await resp.content.read(1024)
                text = body.decode('utf-8', errors='ignore')
                if "udpxy" in text or "Multi stream daemon" in text:
                    return ip_port
    except Exception:
        return None
    return None


async def tcp_filter(ip_ports, concurrency=TCP_CONCURRENCY, label=""):
    """方案二：TCP 预检，快速过滤不可达 IP"""
    sem = asyncio.Semaphore(concurrency)
    total = len(ip_ports)
    passed = []

    async def _probe(ip_port):
        return await tcp_probe(sem, ip_port)

    tasks = [asyncio.create_task(_probe(p)) for p in ip_ports]
    for i, coro in enumerate(asyncio.as_completed(tasks)):
        result = await coro
        if result:
            passed.append(result)
        if (i + 1) % 500 == 0:
            print(f"  [{label}] TCP预检进度 {i+1}/{total}，已通过 {len(passed)} 个")
    return passed


async def http_confirm(ip_ports, url_end, label=""):
    """对 TCP 通过的 IP 发起 HTTP 确认（方案一，aiohttp 异步并发）"""
    sem = asyncio.Semaphore(HTTP_CONCURRENCY)
    timeout = ClientTimeout(total=HTTP_TIMEOUT, connect=0.5)
    connector = TCPConnector(limit=0, limit_per_host=0, ttl_dns_cache=300)
    valid = []
    total = len(ip_ports)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [asyncio.create_task(http_check(session, sem, p, url_end)) for p in ip_ports]
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            result = await coro
            if result:
                valid.append(result)
            if (i + 1) % 500 == 0:
                print(f"  [{label}] HTTP确认进度 {i+1}/{total}，有效 {len(valid)} 个")
    return valid


async def async_scan(ip_ports, url_end, label="", skip_tcp_prefilter=False):
    """
    组合方案：TCP 预检 -> HTTP 确认
    skip_tcp_prefilter=True 时（小列表）可跳过预检直接 HTTP，节省一次握手
    """
    total = len(ip_ports)
    if total == 0:
        return []

    if skip_tcp_prefilter or total <= 300:
        # 列表较小（如仅 d 部分 255 个）直接 HTTP 确认，减少一次 TCP 握手开销
        print(f"  [{label}] 候选 {total} 个，直接 HTTP 确认")
        return await http_confirm(ip_ports, url_end, label=label)

    # 大列表先 TCP 预检
    print(f"  [{label}] 候选 {total} 个，开始 TCP 预检...")
    passed = await tcp_filter(ip_ports, label=label)
    print(f"  [{label}] TCP预检通过 {len(passed)}/{total}，开始 HTTP 确认")
    if not passed:
        return []
    return await http_confirm(passed, url_end, label=label)


# ============ 扫描策略（分级逻辑保持不变，改为调用异步核心） ============
def scan_ip_port_with_option(ip, port, option, loop):
    """有 option 值时，按原脚本逻辑扫描"""
    url_end = "/status" if option >= 10 else "/stat"
    a, b, c_full, d = ip.split('.')
    c_str = c_full  # 可能带 "-"

    if option == 2 or option == 12:
        c_extent = c_str.split('-')
        c_first = int(c_extent[0]) if len(c_extent) == 2 else int(c_extent[0])
        c_last = int(c_extent[1]) + 1 if len(c_extent) == 2 else int(c_extent[0]) + 8
        ip_ports = [f"{a}.{b}.{x}.{y}:{port}" for x in range(c_first, c_last) for y in range(1, 256)]
    elif option == 0 or option == 10:
        ip_ports = [f"{a}.{b}.{c_str}.{y}:{port}" for y in range(1, 256)]
    else:
        ip_ports = [f"{a}.{b}.{x}.{y}:{port}" for x in range(256) for y in range(1, 256)]

    return loop.run_until_complete(
        async_scan(ip_ports, url_end, label=f"option={option}")
    )


def scan_ip_port_without_option(ip, port, loop):
    """
    无 option 值时分级扫描：
    1) 先扫描 d 部分（1-255），c 固定
    2) 若 d 部分无可用 ip，则同时扫描 c、d 两部分：
       - 配置中 c 用 "-" 划分区间，按区间扫描
       - 否则 c 在原数值基础上 +10（即 c 到 c+9，共10段）
    并发数量按 300+
    """
    url_end = "/status"
    a, b, c_full, d = ip.split('.')
    c_base = int(c_full)

    # ---- 第 1 步：仅扫描 d 部分 ----
    print(f"  无option：第1步 扫描 d 部分 {a}.{b}.{c_full}.1-255")
    ip_ports_d = generate_ip_ports_d_only(f"{a}.{b}", port, c_full, d)
    # d 部分仅 255 个，直接 HTTP 确认（跳过 TCP 预检）
    valid = loop.run_until_complete(
        async_scan(ip_ports_d, url_end, label="d部分", skip_tcp_prefilter=True)
    )

    if valid:
        print(f"  d 部分扫描到 {len(valid)} 个有效 ip，结束扫描")
        return valid

    # ---- 第 2 步：d 部分无可用 ip，扫描 c、d 两部分 ----
    if '-' in c_full:
        c_extent = c_full.split('-')
        c_first = int(c_extent[0])
        c_last = int(c_extent[1]) + 1
        print(f"  d 部分无可用ip：第2步 按配置区间扫描 c({c_extent[0]}-{c_extent[1]}) + d(1-255)")
    else:
        c_first = c_base
        c_last = c_base + 10   # 原数值 +10（c 到 c+9，共10段）
        print(f"  d 部分无可用ip：第2步 自动划分区间 c({c_base}-{c_last-1}) + d(1-255)")

    ip_ports_cd = generate_ip_ports_cd(f"{a}.{b}", port, c_first, c_last)
    valid = loop.run_until_complete(
        async_scan(ip_ports_cd, url_end, label="cd部分")
    )
    print(f"  c+d 部分扫描完成，有效 ip：{len(valid)} 个")
    return valid


# ============ 主流程 ============
def process_config(config_file):
    """处理单个配置文件"""
    filename = os.path.basename(config_file)
    province = filename.split('_')[0]
    print(f"{'='*25}\n   获取: {province} ip_port\n{'='*25}")

    configs = read_config(config_file)
    print(f"读取完成，共需扫描 {len(configs)} 组")

    all_ip_ports = []
    loop = asyncio.new_event_loop()
    try:
        for ip_part, port, option in configs:
            if option is not None:
                print(f"\n开始扫描(有option)  http://{ip_part}:{port}  option={option}")
                valid = scan_ip_port_with_option(ip_part, port, option, loop)
            else:
                print(f"\n开始扫描(无option)  http://{ip_part}:{port}")
                valid = scan_ip_port_without_option(ip_part, port, loop)
            all_ip_ports.extend(valid)
    finally:
        loop.close()

    # 去重排序后保存
    if all_ip_ports:
        all_ip_ports = sorted(set(all_ip_ports))
        os.makedirs(SAVE_DIR, exist_ok=True)
        save_path = os.path.join(SAVE_DIR, f"{province}_ip.txt")
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(all_ip_ports))
        print(f"\n{province} 扫描完成，获取有效 ip_port 共：{len(all_ip_ports)}个，已保存到 {save_path}\n")
    else:
        print(f"\n{province} 扫描完成，未扫描到有效 ip_port")


def main():
    os.makedirs(SAVE_DIR, exist_ok=True)
    config_files = sorted(glob.glob(os.path.join(BASE_DIR, '*_config.txt')))
    if not config_files:
        print(f"在 {BASE_DIR} 下未找到 *_config.txt 配置文件")
        return
    for config_file in config_files:
        process_config(config_file)
    print("全部配置扫描完成")


if __name__ == "__main__":
    main()
