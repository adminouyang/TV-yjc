#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP 扫描检测脚本（准确率优化版）
功能：扫描 IP:port，检测 udpxy 状态页，保存有效 IP
路径：IP_Scan/checkout_ip/*_config.txt → 结果 *_ip.txt
"""

import asyncio
import datetime
import glob
import os
import time

import aiohttp
from aiohttp import ClientTimeout, TCPConnector

# ============ 可调参数（准确率优先） ============
HTTP_CONCURRENCY = 200          # 并发数（降低以提升稳定性）
HTTP_TIMEOUT = 4.0              # 总超时（秒）
HTTP_CONNECT_TIMEOUT = 1.5      # 连接超时（秒）
HTTP_RETRY = 1                  # 失败重试次数
FALLBACK_PATH = True           # 是否开启 /stat ↔ /status 回退
# ==============================================


def read_config(config_file):
    print(f"读取设置文件：{config_file}")
    ip_configs = []
    with open(config_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # 支持两种格式：
            # 1. ip:port,option
            # 2. ip:port（无 option）
            if "," in line:
                ip_port_part, option_str = line.split(",", 1)
                option = int(option_str.strip()) if option_str.strip() else None
            else:
                ip_port_part = line
                option = None

            ip_part, port = ip_port_part.strip().split(':')
            a, b, c, d = ip_part.split('.')

            # 无 option 时保持原始 IP 不变（不修改 C/D 段）
            if option is None:
                ip = ip_part
            else:
                # 有 option 时保持原脚本逻辑
                ip = f"{a}.{b}.{c}.1" if option % 2 == 0 else f"{a}.{b}.1.1"

            # 端点规则（默认 /status，option<10 用 /stat）
            url_end = "/status" if (option is None or option >= 10) else "/stat"

            ip_configs.append((ip, port, option, url_end))
            print(f"第{line_num}行：http://{ip}:{port}{url_end}  option={option} 添加成功")

    return ip_configs


def generate_ip_ports(ip, port, option):
    """按 option 生成扫描列表"""
    a, b, c, d = ip.split('.')

    # option 为 2 或 12：C 段区间扫描
    if option is not None and (option == 2 or option == 12):
        c_extent = c.split('-')
        c_first = int(c_extent[0])
        c_last = int(c_extent[1]) + 1 if len(c_extent) == 2 else int(c) + 1
        return [f"{a}.{b}.{x}.{y}:{port}" for x in range(c_first, c_last) for y in range(1, 256)]

    # option 为 0 或 10：只扫当前 C 段的 D 部分
    elif option is not None and (option == 0 or option == 10):
        return [f"{a}.{b}.{c}.{y}:{port}" for y in range(1, 256)]

    # 其他 option：扫描整个 B 段（C 0-255, D 1-255）
    else:
        return [f"{a}.{b}.{x}.{y}:{port}" for x in range(256) for y in range(1, 256)]


async def check_ip_port_async(session, sem, ip_port, url_end):
    """检查单个 IP:port，支持路径回退"""
    paths = [url_end]
    if FALLBACK_PATH:
        paths.append("/stat" if url_end == "/status" else "/status")

    for attempt in range(HTTP_RETRY + 1):
        for path in paths:
            url = f"http://{ip_port}{path}"
            try:
                async with sem:
                    async with session.get(
                        url,
                        timeout=ClientTimeout(total=HTTP_TIMEOUT,
                                             connect=HTTP_CONNECT_TIMEOUT)
                    ) as resp:
                        if resp.status == 200:
                            body = await resp.content.read(2048)
                            text = body.decode('utf-8', errors='ignore')

                            # 与原脚本关键字保持一致
                            if "Multi stream daemon" in text or "udpxy status" in text:
                                return ip_port
            except (asyncio.TimeoutError, aiohttp.ClientError, OSError):
                if attempt >= HTTP_RETRY:
                    return None
                await asyncio.sleep(0.05)

    return None


async def scan_candidates(ip_ports, url_end):
    """并发扫描一组 IP"""
    if not ip_ports:
        return []

    sem = asyncio.Semaphore(HTTP_CONCURRENCY)
    connector = TCPConnector(limit=0, limit_per_host=30, ttl_dns_cache=300)
    timeout = ClientTimeout(total=HTTP_TIMEOUT, connect=HTTP_CONNECT_TIMEOUT)
    valid = []

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [check_ip_port_async(session, sem, ip, url_end) for ip in ip_ports]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            if result:
                valid.append(result)

    return sorted(set(valid))


async def scan_ip_port(ip, port, option, url_end):
    """单组扫描入口"""
    if option is not None:
        # 有 option：按 option 逻辑扫描
        ip_ports = generate_ip_ports(ip, port, option)
        print(f"开始扫描：{ip}:{port}  (共 {len(ip_ports)} 个)")
        return await scan_candidates(ip_ports, url_end), False

    # 无 option：先扫 D 段
    a, b, c, _ = ip.split('.')
    d_ports = [f"{a}.{b}.{c}.{y}:{port}" for y in range(1, 256)]
    print(f"无 option，开始扫描 D 段：{a}.{b}.{c}.1-255:{port} (共 255 个)")
    valid_d = await scan_candidates(d_ports, url_end)

    if valid_d:
        return valid_d, False

    # D 段无有效，扩展 C 段（C+0 ~ C+9）
    print(f"D 段无有效，扩展 C 段：{c} ~ {int(c)+9}")
    c_ports = [
        f"{a}.{b}.{x}.{y}:{port}"
        for x in range(int(c), int(c) + 10)
        for y in range(1, 256)
    ]
    valid_c = await scan_candidates(c_ports, url_end)
    return valid_c, True


def multicast_province(config_file):
    """处理单个省份配置文件"""
    province = os.path.basename(config_file).split('_')[0]
    print(f"\n{'='*30}\n  处理 {province}\n{'='*30}")

    configs = sorted(set(read_config(config_file)))
    print(f"读取完成，共需扫描 {len(configs)} 组")

    all_valid = []
    for ip, port, option, url_end in configs:
        valid, extended = asyncio.run(scan_ip_port(ip, port, option, url_end))
        all_valid.extend(valid)
        if not valid:
            print(f"  {ip}:{port} 无有效 IP")
        else:
            print(f"  {ip}:{port} 获得 {len(valid)} 个有效 IP")

    if all_valid:
        all_valid = sorted(set(all_valid))
        out_path = os.path.join("IP_Scan", "checkout_ip", f"{province}_ip.txt")
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(all_valid))
        print(f"{province} 扫描完成，有效 IP {len(all_valid)} 个，已保存至 {out_path}")
    else:
        # 无有效 IP 时删除原 IP 文件（符合之前要求）
        old_ip_file = os.path.join("IP_Scan", "checkout_ip", f"{province}_ip.txt")
        if os.path.exists(old_ip_file):
            os.remove(old_ip_file)
            print(f"{province} 无有效 IP，已删除原 IP 文件")


def main():
    start = time.time()
    config_files = glob.glob(os.path.join("IP_Scan", "checkout_ip", "*_config.txt"))
    if not config_files:
        print("未找到配置文件，请检查 IP_Scan/checkout_ip/*_config.txt")
        return

    for config_file in config_files:
        multicast_province(config_file)

    print(f"\n全部扫描完成，耗时 {time.time() - start:.1f} 秒")


if __name__ == "__main__":
    main()
