from threading import Thread
import os
import time
import datetime
from datetime import timezone, timedelta
import glob
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 模拟真实浏览器的User-Agent列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

# 城市特定的测试流地址
CITY_STREAMS = {
    "安徽电信": ["rtp/238.1.79.27:4328"],
    "江苏电信": ["udp/239.49.8.19:9614"],
    "四川电信": ["udp/239.93.0.169:5140"],
}

def get_random_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
        'Range': 'bytes=0-',  # 请求整个流用于测速
    }

def get_test_streams_for_city(city_name):
    """根据城市名称获取测试流地址列表"""
    # 只返回CITY_STREAMS中定义的城市测试流
    if city_name in CITY_STREAMS:
        return CITY_STREAMS[city_name]
    return []

def read_config(config_file):
    """读取配置文件，解析IP:端口和可选的option值"""
    print(f"读取设置文件：{config_file}")
    ip_configs = []
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith("#"):
                    print(f"解析第{line_num}行: {line}")
                    
                    # 解析IP:端口和可选的option值
                    if "," in line:
                        # 格式: IP:端口,option
                        parts = line.split(',', 1)
                        ip_port_part = parts[0].strip()
                        option = int(parts[1].strip()) if parts[1].strip().isdigit() else 0
                    else:
                        # 格式: IP:端口 (默认option=0)
                        ip_port_part = line
                        option = 0
                    
                    if ":" in ip_port_part:
                        ip_part, port = ip_port_part.split(':', 1)
                        ip_parts = ip_part.split('.')
                        if len(ip_parts) == 4:
                            a, b, c, d = ip_parts
                            
                            # 保存原始IP和端口
                            original_ip = f"{a}.{b}.{c}.{d}"
                            
                            # 根据option确定扫描范围
                            if option % 10 == 0:  # 扫描D段
                                ip = f"{a}.{b}.{c}.1"
                            else:  # 扫描C段和D段
                                ip = f"{a}.{b}.1.1"
                            
                            ip_configs.append((original_ip, port, ip, port, option))
                            print(f"生成扫描目标: 原始IP={original_ip}:{port}, 扫描IP={ip}:{port} (option={option})")
        return ip_configs
    except Exception as e:
        print(f"读取文件错误: {e}")
        return []

def read_ip_configs(config_file):
    """读取IP配置文件，只返回IP:端口，用于测试"""
    print(f"读取IP文件：{config_file}")
    ip_ports = []
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith("#"):
                    # 只取IP:端口部分，忽略option
                    if "," in line:
                        ip_port = line.split(',')[0].strip()
                    else:
                        ip_port = line.strip()
                    
                    if ":" in ip_port:
                        ip_ports.append(ip_port)
                        print(f"第{line_num}行: {ip_port}")
        
        print(f"从文件中读取到 {len(ip_ports)} 个IP")
        return ip_ports
    except Exception as e:
        print(f"读取文件错误: {e}")
        return []

def read_ip_results(ip_result_file):
    """读取IP结果文件，格式为每行IP:端口"""
    print(f"读取IP结果文件：{ip_result_file}")
    ip_list = []
    try:
        with open(ip_result_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and ":" in line:
                    # 只取IP:端口部分，忽略可能的速度信息
                    ip_port = line.split()[0] if ' ' in line else line
                    ip_list.append(ip_port)
        print(f"从结果文件中读取到 {len(ip_list)} 个IP")
        return ip_list
    except Exception as e:
        print(f"读取IP结果文件错误: {e}")
        return []

def test_stream_speed(stream_url, timeout=10):
    """测试流媒体速度，返回速度(KB/s)和是否成功"""
    try:
        headers = get_random_headers()
        start_time = time.time()
        
        # 设置超时时间
        response = requests.get(stream_url, headers=headers, timeout=timeout, 
                              verify=False, allow_redirects=True, stream=True)
        
        if response.status_code not in [200, 206]:
            return 0, False
        
        # 读取数据用于测速（200KB）
        downloaded = 0
        chunk_size = 32 * 1024  # 32KB chunks
        max_download = 200 * 1024  # 200KB
        
        for chunk in response.iter_content(chunk_size=chunk_size):
            downloaded += len(chunk)
            if downloaded >= max_download:
                break
        
        end_time = time.time()
        duration = end_time - start_time
        
        if duration > 0:
            speed_kbs = downloaded / duration / 1024  # 转换为KB/s
            return speed_kbs, True
        else:
            return 0, False
            
    except Exception as e:
        return 0, False

def check_single_url(ip_port, province, timeout=10):
    """检查单个URL，直接测试组播流速度"""
    try:
        # 添加随机延迟，避免请求过于频繁
        time.sleep(random.uniform(0.1, 0.5))
        
        # 获取该城市对应的测试流
        test_streams = get_test_streams_for_city(province)
        
        if not test_streams:
            print(f"⚠ 跳过测试: 城市 '{province}' 没有对应的测试流")
            return None, 0, ""
        
        best_speed = 0
        best_stream = ""
        
        for stream_path in test_streams:
            stream_url = f"http://{ip_port}/{stream_path}"
            try:
                speed, success = test_stream_speed(stream_url, timeout)
                
                if success:
                    print(f"✓ {ip_port} - 速度: {speed:.2f} KB/s")
                    if speed > best_speed:
                        best_speed = speed
                        best_stream = stream_path
                else:
                    print(f"× {ip_port} - 不可用")
                    
            except Exception as e:
                print(f"× {ip_port} - 错误: {str(e)}")
        
        # 只有速度大于50KB/s才认为是有效的
        if best_speed > 50:
            print(f"✓ 验证通过: {ip_port} - 最佳速度: {best_speed:.2f} KB/s")
            return ip_port, best_speed, best_stream
        else:
            if best_speed > 0:
                print(f"× 速度不足: {ip_port} - 最佳速度: {best_speed:.2f} KB/s")
            else:
                print(f"× 无响应: {ip_port}")
            return None, 0, ""
        
    except Exception as e:
        print(f"× 检查过程出错: {ip_port} - {str(e)}")
        return None, 0, ""

def test_ip_list(ip_list, province, max_workers=10):
    """测试IP列表，返回可用的IP列表"""
    if not ip_list:
        print("IP列表为空，跳过测试")
        return []
    
    print(f"开始测试 {len(ip_list)} 个IP，使用 {max_workers} 个线程")
    
    available_ips = []  # 存储(ip_port, speed, stream)元组
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_single_url, ip_port, province): ip_port for ip_port in ip_list}
        
        for future in as_completed(futures):
            result = future.result()
            if result[0] is not None:  # 只保存有效的IP
                available_ips.append(result)
    
    # 按速度排序
    available_ips.sort(key=lambda x: x[1], reverse=True)
    
    # 去重
    unique_ips = {}
    for ip_port, speed, stream in available_ips:
        if ip_port not in unique_ips or speed > unique_ips[ip_port][1]:
            unique_ips[ip_port] = (ip_port, speed, stream)
    
    unique_ips = list(unique_ips.values())
    unique_ips.sort(key=lambda x: x[1], reverse=True)
    
    print(f"测试完成，找到 {len(unique_ips)} 个可用IP")
    return unique_ips

def generate_ip_ports(ip, port, option):
    """根据option值生成要扫描的IP地址列表"""
    parts = ip.split('.')
    if len(parts) != 4:
        print(f"无效的IP格式: {ip}")
        return []
        
    a, b, c, d = parts
    opt = option % 10  # 只取个位数
    
    print(f"生成IP范围: 基础IP={ip}, 端口={port}, option={opt}")
    
    # 根据option值生成不同的IP范围
    if opt == 0:  # 扫描D段：x.x.x.1-254
        # 只扫描部分IP，提高效率
        ip_list = [f"{a}.{b}.{c}.{y}" for y in range(1, 255, 3)]  # 每3个IP扫描一个
        print(f"扫描D段: 共{len(ip_list)}个IP")
    elif opt == 1:  # 扫描C段和D段
        c_val = int(c)
        if c_val < 254:
            ip_list = ([f"{a}.{b}.{c}.{y}" for y in range(1, 255, 3)] + 
                      [f"{a}.{b}.{c_val+1}.{y}" for y in range(1, 255, 3)])
            print(f"扫描C段和D段: 共{len(ip_list)}个IP")
        else:
            ip_list = [f"{a}.{b}.{c}.{y}" for y in range(1, 255, 3)]
            print(f"扫描D段(边界情况): 共{len(ip_list)}个IP")
    elif opt == 2:  # 扫描指定范围的C段
        c_extent = c.split('-')
        if len(c_extent) == 2:
            c_first = int(c_extent[0])
            c_last = int(c_extent[1]) + 1
            ip_list = [f"{a}.{b}.{x}.{y}" for x in range(c_first, c_last, 2) for y in range(1, 255, 5)]
            print(f"扫描C段范围 {c_first}-{c_last-1}: 共{len(ip_list)}个IP")
        else:
            ip_list = [f"{a}.{b}.{c}.{y}" for y in range(1, 255, 3)]
            print(f"扫描D段: 共{len(ip_list)}个IP")
    else:  # 默认扫描整个B段
        # 大幅减少扫描范围
        ip_list = [f"{a}.{b}.{x}.{y}" for x in range(1, 254, 10) for y in range(1, 255, 10)]
        print(f"扫描整个B段: 共{len(ip_list)}个IP")
    
    # 添加端口
    ip_ports = [f"{ip}:{port}" for ip in ip_list]
    return ip_ports

def scan_ip_port(ip, port, option, province):
    """扫描IP端口"""
    def show_progress():
        start_time = time.time()
        while checked[0] < len(ip_ports):
            elapsed = time.time() - start_time
            rate = checked[0] / elapsed if elapsed > 0 else 0
            valid_count = len([x for x in valid_results if x is not None])
            print(f"进度: {checked[0]}/{len(ip_ports)} ({checked[0]/len(ip_ports)*100:.1f}%), "
                  f"有效: {valid_count}, 速率: {rate:.1f}个/秒, 耗时: {elapsed:.1f}秒")
            time.sleep(10)
    
    valid_results = []  # 存储(ip_port, speed, stream)元组
    ip_ports = generate_ip_ports(ip, port, option)
    
    if not ip_ports:
        print("没有生成有效的IP列表")
        return []
    
    checked = [0]
    
    # 显示进度
    Thread(target=show_progress, daemon=True).start()
    
    # 降低并发数，提高稳定性
    max_workers = 5
    print(f"开始扫描 {province}，使用 {max_workers} 个线程")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_single_url, ip_port, province): ip_port for ip_port in ip_ports}
        
        for future in as_completed(futures):
            result = future.result()
            if result[0] is not None:  # 只保存有效的IP
                valid_results.append(result)
            checked[0] += 1
    
    # 按速度排序
    valid_results.sort(key=lambda x: x[1], reverse=True)
    
    # 去重
    unique_results = {}
    for ip_port, speed, stream in valid_results:
        if ip_port not in unique_results or speed > unique_results[ip_port][1]:
            unique_results[ip_port] = (ip_port, speed, stream)
    
    unique_results = list(unique_results.values())
    unique_results.sort(key=lambda x: x[1], reverse=True)
    
    print(f"扫描完成，找到 {len(unique_results)} 个有效IP")
    return unique_results

def process_province(province):
    """处理单个省份的IP测试"""
    print(f"\n{'='*50}")
    print(f"开始处理: {province}")
    print(f"{'='*50}")
    
    # 检查城市是否在CITY_STREAMS中
    if province not in CITY_STREAMS:
        print(f"⚠ 跳过处理: 城市 '{province}' 不在CITY_STREAMS中")
        return []
    
    # 读取原IP文件
    config_file = os.path.join('ip', f"{province}.txt")
    if not os.path.exists(config_file):
        print(f"⚠ 配置文件不存在: {config_file}")
        return []
    
    # 步骤1: 读取并测试原IP文件
    print(f"\n步骤1: 测试原IP文件: {config_file}")
    original_ips = read_ip_configs(config_file)
    
    if not original_ips:
        print("原IP文件为空，跳过测试")
        return []
    
    available_ips = test_ip_list(original_ips, province, max_workers=10)
    
    # 更新原IP文件，只保留可用的IP
    with open(config_file, 'w', encoding='utf-8') as f:
        for ip_port, speed, stream in available_ips:
            f.write(f"{ip_port}\n")
    
    # 将可用IP写入*_ip.txt文件
    ip_result_file = os.path.join('ip', f"{province}_ip.txt")
    with open(ip_result_file, 'w', encoding='utf-8') as f:
        for ip_port, speed, stream in available_ips:
            f.write(f"{ip_port} {speed:.2f} KB/s\n")
    
    print(f"✓ 更新原IP文件，保留 {len(available_ips)} 个可用IP")
    print(f"✓ 写入IP结果文件: {ip_result_file}")
    
    # 步骤2: 如果原文件中没有可用IP，从*_ip.txt中读取并测试，并进行扫描
    if not available_ips:
        print(f"\n步骤2: 原文件无可用IP，从IP结果文件测试并进行扫描")
        
        # 首先读取IP结果文件
        if os.path.exists(ip_result_file):
            result_ips = read_ip_results(ip_result_file)
            
            if result_ips:
                print(f"测试IP结果文件中的 {len(result_ips)} 个IP")
                result_available_ips = test_ip_list(result_ips, province, max_workers=10)
                
                if result_available_ips:
                    # 更新IP结果文件
                    with open(ip_result_file, 'w', encoding='utf-8') as f:
                        for ip_port, speed, stream in result_available_ips:
                            f.write(f"{ip_port} {speed:.2f} KB/s\n")
                    
                    # 将可用IP添加到原文件
                    with open(config_file, 'a', encoding='utf-8') as f:
                        for ip_port, speed, stream in result_available_ips:
                            f.write(f"{ip_port}\n")
                    
                    print(f"✓ 从IP结果文件找到 {len(result_available_ips)} 个可用IP")
                    available_ips = result_available_ips
        
        # 如果仍然没有可用IP，进行扫描
        if not available_ips:
            print(f"\n步骤3: 进行IP扫描")
            # 读取完整配置（包括option）
            scan_configs = read_config(config_file)
            
            if scan_configs:
                all_scan_results = []
                
                for original_ip, original_port, scan_ip, scan_port, option in scan_configs:
                    print(f"\n扫描配置: 原始IP={original_ip}:{original_port}, 扫描IP={scan_ip}:{scan_port} (option={option})")
                    
                    # 首先测试原始IP
                    original_ip_port = f"{original_ip}:{original_port}"
                    print(f"测试原始IP: {original_ip_port}")
                    original_result = check_single_url(original_ip_port, province)
                    
                    if original_result[0] is not None:
                        print(f"✓ 原始IP有效: {original_ip_port}")
                        all_scan_results.append(original_result)
                    else:
                        # 原始IP无效，进行扫描
                        print(f"× 原始IP无效，开始扫描")
                        scan_results = scan_ip_port(scan_ip, scan_port, option, province)
                        all_scan_results.extend(scan_results)
                        print(f"本组扫描完成，找到 {len(scan_results)} 个有效IP")
                    
                    # 每组处理后休息一下
                    time.sleep(3)
                
                if all_scan_results:
                    # 去重
                    unique_results = {}
                    for ip_port, speed, stream in all_scan_results:
                        if ip_port not in unique_results or speed > unique_results[ip_port][1]:
                            unique_results[ip_port] = (ip_port, speed, stream)
                    
                    available_ips = list(unique_results.values())
                    available_ips.sort(key=lambda x: x[1], reverse=True)
                    
                    # 更新IP结果文件
                    with open(ip_result_file, 'w', encoding='utf-8') as f:
                        for ip_port, speed, stream in available_ips:
                            f.write(f"{ip_port} {speed:.2f} KB/s\n")
                    
                    # 将扫描结果添加到原文件
                    with open(config_file, 'a', encoding='utf-8') as f:
                        for ip_port, speed, stream in available_ips:
                            f.write(f"{ip_port}\n")
                    
                    print(f"✓ 扫描完成，找到 {len(available_ips)} 个可用IP")
                else:
                    print("× 扫描完成，未找到可用IP")
            else:
                print("× 无扫描配置，跳过扫描")
    
    # 显示统计信息
    if available_ips:
        speeds = [speed for _, speed, _ in available_ips]
        avg_speed = sum(speeds) / len(speeds)
        max_speed = max(speeds)
        min_speed = min(speeds)
        print(f"\n✓ {province} 处理完成:")
        print(f"  可用IP数量: {len(available_ips)}")
        print(f"  平均速度: {avg_speed:.2f} KB/s")
        print(f"  最高速度: {max_speed:.2f} KB/s")
        print(f"  最低速度: {min_speed:.2f} KB/s")
    else:
        print(f"\n× {province} 处理完成，未找到可用IP")
    
    return available_ips

def merge_all_results():
    """合并所有省份的结果到总文件"""
    print(f"\n{'='*50}")
    print("合并所有结果")
    print(f"{'='*50}")
    
    all_ips = []
    ip_dir = 'ip'
    
    if not os.path.exists(ip_dir):
        print(f"⚠ IP目录不存在: {ip_dir}")
        return
    
    # 查找所有*_ip.txt文件
    for province in CITY_STREAMS.keys():
        ip_result_file = os.path.join(ip_dir, f"{province}_ip.txt")
        if os.path.exists(ip_result_file):
            try:
                with open(ip_result_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            parts = line.split()
                            ip_port = parts[0]
                            speed = parts[1] if len(parts) > 1 else "0 KB/s"
                            all_ips.append((province, ip_port, speed))
                print(f"✓ 合并: {province}_ip.txt")
            except Exception as e:
                print(f"× 读取文件错误 {ip_result_file}: {e}")
    
    if not all_ips:
        print("⚠ 没有找到任何IP结果")
        return
    
    # 生成时间
    try:
        now = datetime.datetime.now(timezone.utc) + timedelta(hours=8)
    except:
        now = datetime.datetime.utcnow() + timedelta(hours=8)
    current_time = now.strftime("%Y/%m/%d %H:%M")
    
    # 写入总文件
    with open("zubo_all.txt", "w", encoding="utf-8") as f:
        f.write(f"{current_time}更新,#genre#\n")
        
        # 按省份分组写入
        for province in CITY_STREAMS.keys():
            province_ips = [(p, ip, sp) for p, ip, sp in all_ips if p == province]
            if province_ips:
                f.write(f"{province},#genre#\n")
                for i, (prov, ip_port, speed) in enumerate(province_ips, 1):
                    f.write(f"{prov}-IP{i},{ip_port}\n")
    
    print(f"✓ 已生成总文件: zubo_all.txt")
    print(f"  总计IP数量: {len(all_ips)}")

def main():
    print("开始IP测试...")
    
    # 创建必要的目录
    os.makedirs('ip', exist_ok=True)
    
    # 处理每个省份
    processed_results = {}
    
    for province in CITY_STREAMS.keys():
        try:
            result = process_province(province)
            processed_results[province] = result
            # 每个省份处理后休息一下
            time.sleep(2)
        except Exception as e:
            print(f"× 处理 {province} 时出错: {e}")
    
    # 合并所有结果
    merge_all_results()
    
    print(f"\n{'='*50}")
    print("IP测试完成")
    print(f"{'='*50}")
    
    # 显示总体统计
    total_ips = 0
    for province, ips in processed_results.items():
        if ips:
            print(f"{province}: {len(ips)} 个可用IP")
            total_ips += len(ips)
        else:
            print(f"{province}: 0 个可用IP")
    
    print(f"\n总计: {total_ips} 个可用IP")

if __name__ == "__main__":
    main()
