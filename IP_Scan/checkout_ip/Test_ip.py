#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP 扫描检测脚本（完善版 · 按省份分流）

输入：IP_Scan/checkout_ip/test_ip.txt
    格式：ip:port$省份    例：58.37.152.210:4022$上海电信
输出：IP_Scan/checkout_ip/<省份>_config.txt （有效 IP 追加写入，文件已预创建）
      IP_Scan/checkout_ip/Invalid_ip_file/  （无效 IP 记录）

可用性检测：先 http://IP:PORT/status，失败再 http://IP:PORT/stat

扫描策略（按 IP 是否含 C 段区间）：
  - 无区间（如 58.37.152.210:4022）：
       先扫 D 段(1-255)，凑满 2 个有效即停；
       D 段无有效则转扫 C(1-255)+D(1-255)，凑满 1 个即停
  - 有区间（如 106.59.2-3.195:55555）：
       直接扫 C(区间)+D(1-255)，凑满 1 个即停

test_ip.txt 维护规则：
  - 无区间 IP：两阶段都无有效 → 从 test_ip.txt 删除该行，并记录到 Invalid_ip_file/
  - 有区间 IP：无有效 → 不删除（保留在 test_ip.txt），仍记录到 Invalid_ip_file/
"""

import asyncio
import os
import time

import aiohttp
from aiohttp import ClientTimeout, TCPConnector

# ==================== 可调参数 ====================
BASE_DIR = "IP_Scan/checkout_ip"
INPUT_FILE = os.path.join(BASE_DIR, "test_ip.txt")
INVALID_DIR = os.path.join(BASE_DIR, "Invalid_ip_file")

HTTP_CONCURRENCY = 300        # 并发数
HTTP_TIMEOUT = 4.0            # 总超时(秒)
HTTP_CONNECT_TIMEOUT = 1.0    # 连接超时(秒)
D_STOP_COUNT = 2              # D 段扫描停止阈值（凑满即停）
CD_STOP_COUNT = 1             # C+D / C区间 扫描停止阈值
# =================================================


# ---------------- 输入解析 ----------------

def parse_test_ip_line(line):
    """
    解析 test_ip.txt 单行：ip:port$省份
    返回 (a, b, c_str, d_str, port, has_range, province)
    has_range: c 部分是否含 "-" 区间
    """
    line = line.strip()
    if "$" in line:
        addr, province = line.split("$", 1)
    else:
        addr, province = line, ""
    province = province.strip()
    ip_part, port = addr.strip().split(':')
    a, b, c_str, d_str = ip_part.split('.')
    has_range = '-' in c_str
    return a, b, c_str, d_str, port, has_range, province


def read_test_ip(input_file):
    """
    读取 test_ip.txt，返回：
      raw_lines: 全部原始行（保留，用于后续回写/删除）
      groups:    [(a, b, c_str, d_str, port, has_range, province), ...]
    """
    print(f"读取设置文件：{input_file}")
    raw_lines = []
    groups = []

    if not os.path.exists(input_file):
        print(f"  文件不存在：{input_file}")
        return raw_lines, groups

    with open(input_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if ":" not in stripped:
                continue
            try:
                a, b, c_str, d_str, port, has_range, province = parse_test_ip_line(stripped)
            except Exception as e:
                print(f"第{line_num}行：解析失败，跳过 ({e}) -> {stripped}")
                continue

            if not province:
                print(f"第{line_num}行：缺少省份信息，跳过 -> {stripped}")
                continue

            c_disp = c_str if has_range else c_str
            print(f"第{line_num}行：http://{a}.{b}.{c_disp}.{d_str}:{port}/status 添加成功  ({province})")
            raw_lines.append(stripped)
            groups.append((a, b, c_str, d_str, port, has_range, province))

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
    for path in ["/status", "/stat"]:
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
    if not ip_ports:
        return valid

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
        for t in tasks:
            if not t.done():
                t.cancel()

    return valid


async def scan_group(a, b, c_str, d_str, port, has_range):
    """扫描一组配置，返回该组有效 IP 列表（去重）"""
    sem = asyncio.Semaphore(HTTP_CONCURRENCY)
    connector = TCPConnector(limit=0, limit_per_host=30, ttl_dns_cache=300)
    timeout = ClientTimeout(total=HTTP_TIMEOUT, connect=HTTP_CONNECT_TIMEOUT)

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


# ---------------- 结果回写 ----------------

def append_to_config(province, valid_ips):
    """将有效 IP 追加写入 <省份>_config.txt（去重追加，不破坏已有内容）"""
    config_path = os.path.join(BASE_DIR, f"{province}_config.txt")
    # 读取已有内容，避免重复追加同一 IP
    existing = set()
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    existing.add(line.split(',')[0].strip())
    new_ips = [ip for ip in valid_ips if ip not in existing]

    if new_ips:
        with open(config_path, 'a', encoding='utf-8') as f:
            for ip in new_ips:
                f.write(ip + "\n")
        print(f"  追加 {len(new_ips)} 个有效 IP 至 {config_path}")
    else:
        print(f"  无新增有效 IP（{config_path} 已包含所有结果）")

    return new_ips


def write_invalid_records(province, invalid_ips):
    """将无效 IP 记录到 Invalid_ip_file/<省份>_invalid.txt"""
    if not invalid_ips:
        return
    os.makedirs(INVALID_DIR, exist_ok=True)
    invalid_path = os.path.join(INVALID_DIR, f"{province}_invalid.txt")
    with open(invalid_path, 'a', encoding='utf-8') as f:
        for ip in invalid_ips:
            f.write(ip + "\n")
    print(f"  无效 IP 已记录至 {invalid_path} ({len(invalid_ips)} 条)")


def rewrite_test_ip(kept_raw_lines):
    """将保留的行回写 test_ip.txt（去掉已成功分流的有效行）"""
    with open(INPUT_FILE, 'w', encoding='utf-8') as f:
        for line in kept_raw_lines:
            f.write(line + "\n")


# ---------------- 主流程 ----------------

def main():
    start = time.time()
    os.makedirs(INVALID_DIR, exist_ok=True)

    raw_lines, groups = read_test_ip(INPUT_FILE)
    print(f"\n读取完成，共需扫描 {len(groups)} 组")

    if not groups:
        print("无有效配置，跳过")
        return

    # 按省份收集：有效 IP / 无效 IP / 需保留在 test_ip.txt 的原始行
    # province_results[province] = {
    #     "valid": [], "invalid": [], "kept_raw": []
    # }
    province_results = {}

    for idx, (a, b, c_str, d_str, port, has_range, province) in enumerate(groups, 1):
        if province not in province_results:
            province_results[province] = {"valid": [], "invalid": [], "kept_raw": []}
        res = province_results[province]

        original_raw = f"{a}.{b}.{c_str}.{d_str}:{port}${province}"
        original_addr = f"{a}.{b}.{c_str}.{d_str}:{port}"

        print(f"\n--- 第 {idx}/{len(groups)} 组 ({province}) ---")
        valid = asyncio.run(scan_group(a, b, c_str, d_str, port, has_range))

        if valid:
            res["valid"].extend(valid)
            res["kept_raw"].append(original_raw)   # 有效：从 test_ip.txt 移除（不保留）
            print(f"  本组获得 {len(valid)} 个有效 IP")
        else:
            print(f"  本组无有效 IP")
            res["invalid"].append(original_addr)
            if has_range:
                # 有区间：保留在 test_ip.txt，不删除
                res["kept_raw"].append(original_raw)
                print(f"  有区间配置，保留在 {os.path.basename(INPUT_FILE)}：{original_addr}")
            else:
                # 无区间：从 test_ip.txt 删除（不加入 kept_raw）
                print(f"  无区间配置，从 {os.path.basename(INPUT_FILE)} 删除：{original_addr}")

    # 汇总回写：按省份追加有效 IP 到 *_config.txt
    print(f"\n{'='*30}\n  汇总保存\n{'='*30}")
    for province in sorted(province_results.keys()):
        res = province_results[province]

        # 有效 IP 追加到省份 config（去重）
        if res["valid"]:
            all_valid = sorted(set(res["valid"]))
            append_to_config(province, all_valid)
            print(f"{province} 本轮有效 IP {len(all_valid)} 个，已追加至 {province}_config.txt")

        # 无效 IP 记录
        if res["invalid"]:
            write_invalid_records(province, sorted(set(res["invalid"])))

    # 回写 test_ip.txt：仅保留「有区间且无效」的行
    kept_all = []
    for province in sorted(province_results.keys()):
        kept_all.extend(province_results[province]["kept_raw"])
    rewrite_test_ip(kept_all)

    print(f"\n全部扫描完成，耗时 {time.time() - start:.1f} 秒")


if __name__ == "__main__":
    main()
