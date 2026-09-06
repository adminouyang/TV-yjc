import asyncio
import datetime
import glob
import os
import time

import aiohttp
from aiohttp import ClientTimeout, TCPConnector

# ============ 可调参数 ============
TCP_PROBE_ENABLED = False        # 关闭TCP预检（提高准确率）
TCP_TIMEOUT = 1.0                # 若开启预检，TCP超时(秒)
TCP_CONCURRENCY = 300
HTTP_TIMEOUT = 3.0               # HTTP总超时(秒)
HTTP_CONNECT_TIMEOUT = 1.0       # HTTP连接超时(秒)
HTTP_CONCURRENCY = 300           # HTTP并发数（降低以提升稳定性）
HTTP_RETRY = 1                   # HTTP失败重试次数
# ==================================


def read_config(config_file):
    print(f"读取设置文件：{config_file}")
    ip_configs = []
    try:
        with open(config_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                if "," in line and not line.startswith("#"):
                    parts = line.strip().split(',')
                    ip_part, port = parts[0].strip().split(':')
                    a, b, c, d = ip_part.split('.')
                    # 无option时 -> None
                    option = int(parts[1]) if len(parts) > 1 and parts[1].strip() else None
                    url_end = "/status" if (option is None or option >= 10) else "/stat"
                    if option is None:
                        ip = ip_part
                    else:
                        ip = f"{a}.{b}.{c}.1" if option % 2 == 0 else f"{a}.{b}.1.1"
                    ip_configs.append((ip, port, option, url_end))
                    print(f"第{line_num}行：http://{ip}:{port}{url_end} 添加到扫描列表")
        return ip_configs
    except Exception as e:
        print(f"读取文件错误: {e}")
        return []


def generate_ip_ports(ip, port, option):
    a, b, c, d = ip.split('.')
    if option is not None and (option == 2 or option == 12):
        c_extent = c.split('-')
        c_first = int(c_extent[0])
        c_last = int(c_extent[1]) + 1 if len(c_extent) == 2 else int(c) + 1
        return [f"{a}.{b}.{x}.{y}:{port}" for x in range(c_first, c_last) for y in range(1, 256)]
    elif option is not None and (option == 0 or option == 10):
        return [f"{a}.{b}.{c}.{y}:{port}" for y in range(1, 256)]
    else:
        c_extent = c.split('-')
        c_first = int(c_extent[0])
        c_last = int(c_extent[1]) + 1 if len(c_extent) == 2 else int(c) + 1
        return [f"{a}.{b}.{x}.{y}:{port}" for x in range(c_first, c_last) for y in range(1, 256)]


async def probe_tcp(sem, ip_port, timeout=TCP_TIMEOUT):
    host, port = ip_port.rsplit(':', 1)
    try:
        async with sem:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, int(port)),
                timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            return ip_port
    except:
        return None

async def check_ip_port_async(session, sem, ip_port, url_end):
    # 尝试的路径列表：优先配置的路径，失败后再试另一个
    alternative_end = "/stat" if url_end == "/status" else "/status"
    
    for attempt_end in [url_end, alternative_end]:
        url = f"http://{ip_port}{attempt_end}"
        try:
            async with sem:
                async with session.get(url, timeout=... ) as resp:
                    if resp.status == 200:
                        body = await resp.content.read(2048)
                        text = body.decode('utf-8', errors='ignore')
                        if "udpxy" in text or "Multi stream daemon" in text:
                            return ip_port
        except:
            continue
    return None

# async def check_ip_port_async(session, sem, ip_port, url_end):
#     url = f"http://{ip_port}{url_end}"
#     for attempt in range(HTTP_RETRY + 1):
#         try:
#             async with sem:
#                 async with session.get(
#                     url,
#                     timeout=ClientTimeout(total=HTTP_TIMEOUT,
#                                          connect=HTTP_CONNECT_TIMEOUT)
#                 ) as resp:
#                     if resp.status == 200:
#                         body = await resp.content.read(2048)
#                         text = body.decode('utf-8', errors='ignore')
#                         if "udpxy" in text or "Multi stream daemon" in text:
#                             return ip_port
#         except (asyncio.TimeoutError, aiohttp.ClientError, OSError):
#             if attempt == HTTP_RETRY:
#                 return None
#             await asyncio.sleep(0.05)
#     return None


async def scan_candidates(ip_ports, url_end):
    if not ip_ports:
        return []

    # TCP预检（默认关闭）
    if TCP_PROBE_ENABLED and len(ip_ports) > 300:
        sem_probe = asyncio.Semaphore(TCP_CONCURRENCY)
        total_before = len(ip_ports)
        tasks = [probe_tcp(sem_probe, ip) for ip in ip_ports]
        results = await asyncio.gather(*tasks)
        ip_ports = [x for x in results if x]
        print(f"  TCP预检通过 {len(ip_ports)}/{total_before}")

    # HTTP确认
    sem_http = asyncio.Semaphore(HTTP_CONCURRENCY)
    connector = TCPConnector(limit=0, limit_per_host=50, ttl_dns_cache=300)
    timeout = ClientTimeout(total=HTTP_TIMEOUT, connect=HTTP_CONNECT_TIMEOUT)
    valid = []

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [check_ip_port_async(session, sem_http, ip, url_end) for ip in ip_ports]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            if result:
                valid.append(result)

    return sorted(set(valid))


async def scan_ip_port(ip, port, option, url_end):
    """扫描入口：兼容有/无option两种逻辑"""
    if option is not None:
        print(f"\n开始扫描 http://{ip}:{port}{url_end}")
        ip_ports = generate_ip_ports(ip, port, option)
        valid = await scan_candidates(ip_ports, url_end)
        return valid, False

    # 无option：先扫d部分
    a, b, c, _ = ip.split('.')
    d_ports = [f"{a}.{b}.{c}.{y}:{port}" for y in range(1, 256)]
    print(f"\n开始扫描 http://{ip}:{port}{url_end}（仅d段）")
    valid_d = await scan_candidates(d_ports, url_end)

    if valid_d:
        return valid_d, False

    # d段无有效，扩展c+10
    print(f"d段无有效IP，扩展c段扫描 {c}~{int(c)+9}")
    c_ports = [
        f"{a}.{b}.{x}.{y}:{port}"
        for x in range(int(c), int(c) + 10)
        for y in range(1, 256)
    ]
    valid_c = await scan_candidates(c_ports, url_end)
    return valid_c, True  # 返回有效列表和是否扩展标志


def save_results(province, all_ip_ports):
    if not all_ip_ports:
        print(f"\n{province} 扫描完成，未扫描到有效ip_port")
        return

    all_ip_ports = sorted(set(all_ip_ports))
    print(f"\n{province} 扫描完成，获取有效ip_port共：{len(all_ip_ports)}个")

    out_path = os.path.join("IP_Scan", "checkout_ip", f"{province}_ip.txt")
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(all_ip_ports))
    print(f"结果已保存到 {out_path}")


def multicast_province(config_file):
    filename = os.path.basename(config_file)
    province = filename.split('_')[0]
    print(f"\n{'='*25}\n   获取: {province} ip_port\n{'='*25}")

    configs = sorted(set(read_config(config_file)))
    print(f"读取完成，共需扫描 {len(configs)} 组")

    all_ip_ports = []
    for ip, port, option, url_end in configs:
        valid, extended = asyncio.run(scan_ip_port(ip, port, option, url_end))
        all_ip_ports.extend(valid)
        if option is None and not valid:
            # 无option且d段无有效已自动扩展，无需额外处理
            pass

    save_results(province, all_ip_ports)


def main():
    start = time.time()
    config_files = glob.glob(os.path.join("IP_Scan", "checkout_ip", "*_config.txt"))
    for config_file in config_files:
        multicast_province(config_file)
    print(f"\n全部扫描完成，耗时 {time.time() - start:.1f} 秒")


if __name__ == "__main__":
    main()
