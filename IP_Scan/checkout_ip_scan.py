#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP 扫描与有效性检测脚本
功能：读取 IP_Scan/checkout_ip/*_config.txt 配置文件，扫描有效 ip:port 并保存
去除原脚本中生成节目源（template/zubo）相关逻辑
"""
from threading import Thread
import os
import time
import glob
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed


# ============ 配置区 ============
BASE_DIR = "IP_Scan/checkout_ip"
SAVE_DIR = "IP_Scan/checkout_ip"   # 有效 ip 保存目录（同目录下 *_ip.txt）


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
                    option = int(parts[1].strip()) if len(parts) > 1 else None
                    port = port.strip()
                    ip_configs.append((ip_part, port, option))
                    url_end = "/status" if option is not None and option >= 10 else "/stat"
                    print(f"第{line_num}行：{ip_part}:{port} option={option} 添加到扫描列表 (检测路径{url_end})")
        return ip_configs
    except Exception as e:
        print(f"读取文件错误: {e}")
        return []


def generate_ip_ports_d_only(ip, port, c_str, d_str):
    """仅扫描 d 部分（1-255），c 固定"""
    c = int(c_str)
    return [f"{ip}.{c}.{d}:{port}" for d in range(1, 256)]


def generate_ip_ports_cd(ip, port, c_first, c_last):
    """同时扫描 c 部分 [c_first, c_last) 与 d 部分 (1-255)"""
    return [f"{ip}.{c}.{d}:{port}" for c in range(c_first, c_last) for d in range(1, 256)]


def check_ip_port(ip_port, url_end):
    """发送 GET 请求检测 url 是否可访问，返回 ip_port 或 None"""
    try:
        url = f"http://{ip_port}{url_end}"
        resp = requests.get(url, timeout=2)
        resp.raise_for_status()
        if "Multi stream daemon" in resp.text or "udpxy status" in resp.text:
            # print(f"{url} 访问成功")
            return ip_port
    except Exception:
        return None
    return None


def scan_with_workers(ip_ports, url_end, max_workers, label=""):
    """多线程扫描，返回有效 ip_port 列表"""
    def show_progress():
        while checked[0] < total:
            print(f"[{label}] 已扫描：{checked[0]}/{total}, 有效ip_port：{len(valid)}个")
            time.sleep(30)

    valid = []
    total = len(ip_ports)
    checked = [0]
    if total == 0:
        return valid

    Thread(target=show_progress, daemon=True).start()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_ip_port, ip_port, url_end): ip_port for ip_port in ip_ports}
        for future in as_completed(futures):
            result = future.result()
            if result:
                valid.append(result)
            checked[0] += 1
    return valid


def scan_ip_port_with_option(ip, port, option):
    """有 option 值时，按原脚本逻辑扫描"""
    url_end = "/status" if option >= 10 else "/stat"
    a, b, c_full, d = ip.split('.')
    c_str = c_full  # 可能带 "-"

    # option 偶数：扫描 c(可能区间) + d
    if option == 2 or option == 12:
        c_extent = c_str.split('-')
        c_first = int(c_extent[0]) if len(c_extent) == 2 else int(c_extent[0])
        c_last = int(c_extent[1]) + 1 if len(c_extent) == 2 else int(c_extent[0]) + 8
        ip_ports = [f"{a}.{b}.{x}.{y}:{port}" for x in range(c_first, c_last) for y in range(1, 256)]
    elif option == 0 or option == 10:
        # 仅扫描 d 部分
        ip_ports = [f"{a}.{b}.{c_str}.{y}:{port}" for y in range(1, 256)]
    else:
        # 其它 option：全量扫描 c(0-255)+d(1-255)
        ip_ports = [f"{a}.{b}.{x}.{y}:{port}" for x in range(256) for y in range(1, 256)]

    return scan_with_workers(ip_ports, url_end, max_workers=100, label=f"option={option}")


def scan_ip_port_without_option(ip, port):
    """
    无 option 值时分级扫描：
    1) 先扫描 d 部分（1-255），c 固定
    2) 若 d 部分无可用 ip，则同时扫描 c、d 两部分：
       - 若配置中 c 用 "-" 划分区间，按区间扫描
       - 否则 c 在原数值基础上 +10 作为区间上限（即 c 到 c+9）
    并发数量按 300
    """
    url_end = "/status"
    a, b, c_full, d = ip.split('.')
    c_base = int(c_full)

    # ---- 第 1 步：仅扫描 d 部分 ----
    print(f"  无option：第1步 扫描 d 部分 {a}.{b}.{c_full}.1-255")
    ip_ports_d = generate_ip_ports_d_only(f"{a}.{b}", port, c_full, d)
    valid = scan_with_workers(ip_ports_d, url_end, max_workers=100, label="d部分")

    if valid:
        print(f"  d 部分扫描到 {len(valid)} 个有效 ip，结束扫描")
        return valid

    # ---- 第 2 步：d 部分无可用 ip，扫描 c、d 两部分 ----
    # 判断 c 是否有 "-" 区间划分
    if '-' in c_full:
        c_extent = c_full.split('-')
        c_first = int(c_extent[0])
        c_last = int(c_extent[1]) + 1
        print(f"  d 部分无可用ip：第2步 按配置区间扫描 c({c_extent[0]}-{c_extent[1]}) + d(1-255)")
    else:
        c_first = c_base
        c_last = c_base + 10   # 原数值 +10（即 c 到 c+9，共10段）
        print(f"  d 部分无可用ip：第2步 自动划分区间 c({c_base}-{c_last-1}) + d(1-255)")

    ip_ports_cd = generate_ip_ports_cd(f"{a}.{b}", port, c_first, c_last)
    valid = scan_with_workers(ip_ports_cd, url_end, max_workers=300, label="cd部分")
    print(f"  c+d 部分扫描完成，有效 ip：{len(valid)} 个")
    return valid


def process_config(config_file):
    """处理单个配置文件"""
    filename = os.path.basename(config_file)
    province = filename.split('_')[0]
    print(f"{'='*25}\n   获取: {province} ip_port\n{'='*25}")

    configs = read_config(config_file)
    print(f"读取完成，共需扫描 {len(configs)} 组")

    all_ip_ports = []
    for ip_part, port, option in configs:
        if option is not None:
            print(f"\n开始扫描(有option)  http://{ip_part}:{port}  option={option}")
            valid = scan_ip_port_with_option(ip_part, port, option)
        else:
            print(f"\n开始扫描(无option)  http://{ip_part}:{port}")
            valid = scan_ip_port_without_option(ip_part, port)
        all_ip_ports.extend(valid)

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
