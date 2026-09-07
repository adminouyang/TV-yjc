#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP 扫描检测脚本（完善版）

核心规则：
1. 可用性检测分两步：先 http://IP:PORT/status，失败再 http://IP:PORT/stat
2. 去除 option 值，配置每行仅 "ip:port"
3. 扫描策略：
   - 无区间 IP（如 114.226.0.1:4022）：
       先扫 D 段(1-255)，凑满 2 个有效即停；
       D 段无有效则转扫 C(1-255)+D(1-255)，凑满 1 个即停
   - 有区间 IP（如 114.226.208-231.1:8787）：
       直接扫 C(区间)+D(1-255)，凑满 1 个即停
4. 无区间 IP 两阶段都无有效 → 从原 config 删除，并保存到 Invalid_ip_file/
   有区间 IP 无有效 → 不删除，但仍记录到 invalid 文件
5. 详细日志输出
"""

import asyncio
import glob
import os
import time

import aiohttp
from aiohttp import ClientTimeout, TCPConnector

# ==================== 可调参数 ====================
BASE_DIR = "IP_Scan/checkout_ip"
INVALID_DIR = os.path.join(BASE_DIR, "Invalid_ip_file")

HTTP_CONCURRENCY = 300        # 并发数
HTTP_TIMEOUT = 3.0            # 总超时(秒)
HTTP_CONNECT_TIMEOUT = 0.6    # 连接超时(秒)
D_STOP_COUNT = 2              # D 段扫描停止阈值（凑满即停）
CD_STOP_COUNT = 1             # C+D 段扫描停止阈值
# =================================================


# ---------------- 配置解析 ----------------

def parse_ip_line(line):
    """
    解析单行配置，返回 (a, b, c_str, d_str, port, has_range)
    has_range: c 部分是否含 "-" 区间
    """
    line = line.strip()
    ip_part, port = line.split(':')
    a, b, c_str, d_str = ip_part.split('.')
    has_range = '-' in c_str
    return a, b, c_str, d_str, port, has_range


def read_config(config_file):
    """读取配置文件，返回原始行列表 + 解析后的配置组"""
    print(f"\n读取设置文件：{config_file}")
    raw_lines = []      # 保留原始行（用于后续删除/保存）
    groups = []         # (a, b, c_str, d_str, port, has_range)

    with open(config_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if ":" not in stripped:
                continue
            try:
                a, b, c_str, d_str, port, has_range = parse_ip_line(stripped)
            except Exception as e:
                print(f"第{line_num}行：解析失败，跳过 ({e}) -> {stripped}")
                continue

            # 打印添加信息（示例格式）
            if has_range:
                print(f"第{line_num}行：http://{a}.{b}.{c_str}.{d_str}:{port}/status 添加成功")
            else:
                print(f"第{line_num}行：http://{a}.{b}.{c_str}.{d_str}:{port}/status 添加成功")

            raw_lines.append(stripped)
            groups.append((a, b, c_str, d_str, port, has_range))

    return raw_lines, groups


# ---------------- IP 生成 ----------------

def generate_d_only(a, b, c_str, d_str, port):
    """仅 D 段变化（1-255），C 固定"""
    c = int(c_str)
    return [f"{a}.{b}.{c}.{y}:{port}" for y in range(1, 256)]


def generate_cd_full(a, b, c_str, d_str, port):
    """C(1-255) + D(1-255) 全扫"""
    return [f"{a}.{b}.{x}.{y}:{port}" for x in range(1, 256) for y in range(1, 256)]


def generate_c_range(a, b, c_str, d_str, port):
    """C 按区间扫描，D(1-255)"""
    c_first, c_last = c_str.split('-')
    c_first, c_last = int(c_first), int(c_last)
    return [f"{a}.{b}.{x}.{y}:{port}" for x in range(c_first, c_last + 1) for y in range(1, 256)]


# ---------------- 单 IP 检测 ----------------

async def check_one(session, sem, ip_port):
    """
    对单个 ip:port 检测可用性：
    先 /status，失败再 /stat
    返回 (ip_port, path) 或 None
    """
    paths = ["/status", "/stat"]
    for path in paths:
        url = f"http://{ip_port}{path}"
        try:
            async with sem:
                async with session.get(
                    url,
                    timeout=ClientTimeout(total=HTTP_TIMEOUT, connect=HTTP_CONNECT_TIMEOUT)
                ) as resp:
                    if resp.status == 200:
                        body = await resp.content.read(2048)
                        text = body.decode('utf-8', errors='ignore')
                        if "Multi stream daemon" in text or "udpxy" in text:
                            return ip_port, path
        except (asyncio.TimeoutError, aiohttp.ClientError, OSError):
            continue
    return None


# ---------------- 并发扫描（带提前停止） ----------------

async def scan_until(session, sem, ip_ports, stop_count, label):
    """
    并发扫描 ip_ports，每发现一个有效立即打印；
    一旦有效数 >= stop_count 立即取消剩余任务并返回。
    """
    valid = []
    tasks = [asyncio.create_task(check_one(session, sem, ip)) for ip in ip_ports]

    try:
        for coro in asyncio.as_completed(tasks):
            result = await coro
            if result is not None:
                ip_port, path = result
                valid.append(ip_port)
                print(f"  有效 IP: http://{ip_port}{path}")
                if len(valid) >= stop_count:
                    print(f"  ({label}) 已凑满 {stop_count} 个有效 IP，停止扫描")
                    break
    finally:
        # 取消尚未完成的任务，避免无谓请求
        for t in tasks:
            if not t.done():
                t.cancel()

    return valid


async def scan_group(a, b, c_str, d_str, port, has_range):
    """
    扫描一组配置，返回该组有效 IP 列表（去重）
    """
    sem = asyncio.Semaphore(HTTP_CONCURRENCY)
    connector = TCPConnector(limit=0, limit_per_host=30, ttl_dns_cache=300)
    timeout = ClientTimeout(total=HTTP_TIMEOUT, connect=HTTP_CONNECT_TIMEOUT)

    base = f"{a}.{b}"
    all_valid = []

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:

        if not has_range:
            # --- 无区间：先扫 D 段 ---
            ip_ports = generate_d_only(a, b, c_str, d_str, port)
            print(f"开始扫描：{a}.{b}.{c_str}.{d_str}:{port}  (D段 共 {len(ip_ports)} 个)")
            valid = await scan_until(session, sem, ip_ports, D_STOP_COUNT, "D段")
            all_valid.extend(valid)

            if len(all_valid) >= D_STOP_COUNT:
                return sorted(set(all_valid))

            # --- D 段不足，转扫 C+D ---
            print(f"D段有效 {len(all_valid)} 个(<{D_STOP_COUNT})，扩展扫描 C(1-255)+D(1-255)")
            ip_ports_cd = generate_cd_full(a, b, c_str, d_str, port)
            print(f"开始扫描：{a}.{b}.*.{d_str}:{port}  (C+D 共 {len(ip_ports_cd)} 个)")
            valid_cd = await scan_until(session, sem, ip_ports_cd, CD_STOP_COUNT, "C+D段")
            all_valid.extend(valid_cd)

        else:
            # --- 有区间：直接扫 C(区间)+D ---
            ip_ports = generate_c_range(a, b, c_str, d_str, port)
            print(f"开始扫描：{a}.{b}.{c_str}.{d_str}:{port}  (C区间 共 {len(ip_ports)} 个)")
            valid = await scan_until(session, sem, ip_ports, CD_STOP_COUNT, "C区间")
            all_valid.extend(valid)

    return sorted(set(all_valid))


# ---------------- 省份处理 ----------------

def multicast_province(config_file):
    """处理单个省份配置文件"""
    province = os.path.basename(config_file).split('_')[0]
    print(f"\n{'='*30}\n  处理 {province}\n{'='*30}")

    raw_lines, groups = read_config(config_file)
    print(f"\n读取完成，共需扫描 {len(groups)} 组")

    if not groups:
        print("无有效配置，跳过")
        return

    province_valid = []       # 该省所有有效 IP
    invalid_lines = []        # 需记录到 invalid 文件的原始行
    kept_lines = []           # 保留回写原 config 的行

    for idx, (a, b, c_str, d_str, port, has_range) in enumerate(groups, 1):
        print(f"\n--- 第 {idx}/{len(groups)} 组 ---")
        valid = asyncio.run(scan_group(a, b, c_str, d_str, port, has_range))
        original = f"{a}.{b}.{c_str}.{d_str}:{port}"

        if valid:
            province_valid.extend(valid)
            kept_lines.append(original)   # 有有效 → 保留该行
            print(f"  本组获得 {len(valid)} 个有效 IP")
        else:
            print(f"  本组无有效 IP")
            invalid_lines.append(original)
            if has_range:
                # 有区间：不删除，保留原行
                kept_lines.append(original)
                print(f"  有区间配置，保留在原文件中：{original}")
            else:
                # 无区间：从原文件删除（不加入 kept_lines）
                print(f"  无区间配置，从原文件删除：{original}")

    # 回写原 config（去掉被删除的无区间无效行）
    with open(config_file, 'w', encoding='utf-8') as f:
        for line in kept_lines:
            f.write(line + "\n")

    # 保存无效 IP 记录
    if invalid_lines:
        os.makedirs(INVALID_DIR, exist_ok=True)
        invalid_path = os.path.join(INVALID_DIR, f"{province}_invalid.txt")
        with open(invalid_path, 'a', encoding='utf-8') as f:
            for line in invalid_lines:
                f.write(line + "\n")
        print(f"\n无效 IP 已记录至 {invalid_path} ({len(invalid_lines)} 条)")

    # 保存有效 IP
    province_valid = sorted(set(province_valid))
    if province_valid:
        out_path = os.path.join(BASE_DIR, f"{province}_ip.txt")
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(province_valid))
        print(f"{province} 扫描完成，有效 IP {len(province_valid)} 个，已保存至 {out_path}")
    else:
        # 无有效 IP：删除原 IP 文件
        out_path = os.path.join(BASE_DIR, f"{province}_ip.txt")
        if os.path.exists(out_path):
            os.remove(out_path)
        print(f"{province} 扫描完成，无有效 IP")


def main():
    start = time.time()
    os.makedirs(INVALID_DIR, exist_ok=True)

    config_files = glob.glob(os.path.join(BASE_DIR, "*_config.txt"))
    if not config_files:
        print(f"未找到配置文件：{BASE_DIR}/*_config.txt")
        return

    for config_file in sorted(config_files):
        multicast_province(config_file)

    print(f"\n全部扫描完成，耗时 {time.time() - start:.1f} 秒")


if __name__ == "__main__":
    main()
