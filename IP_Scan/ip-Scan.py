from threading import Thread
import os
import time
import glob
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

def expand_ip_range(ip_str):
    """扩展IP范围，返回IP列表"""
    ip_list = []
    
    # 分割IP的四个部分
    parts = ip_str.split('.')
    if len(parts) != 4:
        return [ip_str]
    
    # 扩展每个部分
    a_list = expand_part(parts[0])
    b_list = expand_part(parts[1])
    c_list = expand_part(parts[2])
    d_list = expand_part(parts[3])
    
    # 生成所有IP组合
    for a in a_list:
        for b in b_list:
            for c in c_list:
                for d in d_list:
                    ip_list.append(f"{a}.{b}.{c}.{d}")
    
    return ip_list

def expand_part(part):
    """扩展单个部分，支持范围和单个值"""
    if '-' in part:
        start, end = part.split('-')
        return [str(i) for i in range(int(start), int(end) + 1)]
    else:
        return [part]

def read_config(config_file):
    """读取配置文件，返回配置行列表和原始行列表"""
    print(f"读取设置文件：{config_file}")
    ip_configs = []
    original_lines = []
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for line_num, line in enumerate(lines, 1):
            original_line = line.rstrip('\n')
            original_lines.append(original_line)
            line = line.strip()
            
            if not line or line.startswith("#"):
                continue
                
            try:
                if "," in line:
                    parts = line.split(',')
                    ip_part_port = parts[0].strip()
                    option = int(parts[1])
                else:
                    ip_part_port = line.strip()
                    option = 12
                
                if ":" not in ip_part_port:
                    print(f"第{line_num}行格式错误: 缺少端口号 - {line}")
                    continue
                    
                # 分离IP和端口
                ip_part, port = ip_part_port.split(':')
                
                # 检查是否是带范围的IP
                if '-' in ip_part:
                    # 扩展带范围的IP
                    expanded_ips = expand_ip_range(ip_part)
                    print(f"  第{line_num}行IP扩展: {ip_part} -> {len(expanded_ips)} 个IP")
                    
                    # 为每个扩展的IP创建配置
                    for expanded_ip in expanded_ips:
                        ip_parts = expanded_ip.split('.')
                        a, b, c, d = ip_parts
                        url_end = "/status" if option >= 10 else "/stat"
                        base_ip = f"{a}.{b}.{c}.1" if option % 2 == 0 else f"{a}.{b}.1.1"
                        
                        ip_configs.append((base_ip, port, option, url_end, line_num-1, f"{expanded_ip}:{port},{option}" if "," in line else f"{expanded_ip}:{port}"))
                else:
                    # 原来的逻辑，处理普通IP
                    ip_parts = ip_part.split('.')
                    if len(ip_parts) != 4:
                        print(f"第{line_num}行格式错误: IP地址格式不正确 - {line}")
                        continue
                    
                    a, b, c, d = ip_parts
                    url_end = "/status" if option >= 10 else "/stat"
                    base_ip = f"{a}.{b}.{c}.1" if option % 2 == 0 else f"{a}.{b}.1.1"
                    
                    ip_configs.append((base_ip, port, option, url_end, line_num-1, original_line))
                    
            except Exception as e:
                print(f"第{line_num}行格式错误: {e} - {line}")
                continue
                
        return ip_configs, original_lines
    except Exception as e:
        print(f"读取文件错误: {e}")
        return [], []

def generate_ip_ports(ip, port, option):
    """根据选项生成要扫描的IP地址列表"""
    a, b, c, d = ip.split('.')
    
    if option == 2 or option == 12:
        c_extent = c.split('-')
        c_first = int(c_extent[0]) if len(c_extent) == 2 else int(c)
        c_last = int(c_extent[1]) + 1 if len(c_extent) == 2 else int(c) + 8
        return [f"{a}.{b}.{x}.{y}:{port}" for x in range(c_first, c_last) for y in range(1, 256)]
    elif option == 0 or option == 10:
        return [f"{a}.{b}.{c}.{y}:{port}" for y in range(1, 256)]
    else:
        return [f"{a}.{b}.{x}.{y}:{port}" for x in range(256) for y in range(1, 256)]

def check_ip_port(ip_port, url_end):    
    """检查IP端口是否可用"""
    try:
        url = f"http://{ip_port}{url_end}"
        resp = requests.get(url, timeout=2)
        resp.raise_for_status()
        if "Multi stream daemon" in resp.text or "udpxy status" in resp.text:
            return ip_port
    except:
        return None

def scan_ip_port(ip, port, option, url_end):
    """扫描IP端口"""
    def show_progress():
        while checked[0] < len(ip_ports) and option % 2 == 1:
            time.sleep(5)
    
    valid_ip_ports = []
    ip_ports = generate_ip_ports(ip, port, option)
    checked = [0]
    
    if option % 2 == 1:
        Thread(target=show_progress, daemon=True).start()
    
    with ThreadPoolExecutor(max_workers = 300 if option % 2 == 1 else 100) as executor:
        futures = {executor.submit(check_ip_port, ip_port, url_end): ip_port for ip_port in ip_ports}
        for future in as_completed(futures):
            result = future.result()
            if result:
                valid_ip_ports.append(result)
            checked[0] += 1
    
    return valid_ip_ports

def process_config_file(config_file):
    """处理配置文件，扫描并返回有效IP"""
    filename = os.path.basename(config_file)
    province_name = os.path.splitext(filename)[0].replace("_good_ip", "")
    print(f"\n{'='*25}\n   处理: {province_name}\n{'='*25}")
    
    # 读取配置
    configs, original_lines = read_config(config_file)
    if not configs:
        print(f"配置文件 {filename} 中没有有效的配置行")
        return []
    
    # 准备记录扫描结果
    all_valid_ip_ports = []
    
    # 记录扫描进度
    total_configs = len(configs)
    
    for idx, (ip, port, option, url_end, line_num, original_line) in enumerate(configs, 1):
        print(f"\n[{idx}/{total_configs}] 扫描: {original_line}")
        valid_ips = scan_ip_port(ip, port, option, url_end)
        
        if valid_ips:
            all_valid_ip_ports.extend(valid_ips)
            print(f"  找到 {len(valid_ips)} 个有效IP")
        else:
            print(f"  没有找到有效IP")
    
    return all_valid_ip_ports

def main():
    # 确保输入目录存在
    ip_dir = "IP_Scan/ip"
    if not os.path.exists(ip_dir):
        os.makedirs(ip_dir)
        print(f"创建目录: {ip_dir}")
    
    # 确保输出目录存在
    result_dir = "IP_Scan/result_ip"
    if not os.path.exists(result_dir):
        os.makedirs(result_dir)
        print(f"创建目录: {result_dir}")
    
    # 获取ip目录下所有以_good_ip.txt结尾的文件
    config_files = glob.glob(os.path.join(ip_dir, "*_good_ip.txt"))
    
    if not config_files:
        print(f"在 '{ip_dir}' 目录下未找到以'_good_ip.txt'结尾的配置文件")
        return
    
    print(f"找到 {len(config_files)} 个配置文件")
    
    # 处理所有配置文件
    for config_file in config_files:
        filename = os.path.basename(config_file)
        province_name = os.path.splitext(filename)[0].replace("_good_ip", "")
        
        valid_ip_ports = process_config_file(config_file)
        
        if valid_ip_ports:
            valid_ip_ports = sorted(set(valid_ip_ports))
            result_filename = f"{province_name}.txt"
            result_path = os.path.join(result_dir, result_filename)
            
            # 如果文件已存在，追加写入
            mode = 'a' if os.path.exists(result_path) else 'w'
            existing_ips = set()
            
            # 读取已存在的IP
            if mode == 'a':
                try:
                    with open(result_path, 'r', encoding='utf-8') as f:
                        existing_ips = set(line.strip() for line in f if line.strip())
                except:
                    existing_ips = set()
            
            # 去重并写入
            all_ips = sorted(set(list(existing_ips) + valid_ip_ports))
            
            with open(result_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(all_ips))
            
            new_count = len(all_ips) - len(existing_ips)
            print(f"{province_name}: 保存 {len(all_ips)} 个有效IP到 {result_filename} (新增 {new_count} 个)")
        else:
            print(f"{province_name}: 没有找到有效IP")
        
        print("-" * 50)
    
    print(f"\nIP地址扫描完成")
    print(f"扫描结果保存在 {result_dir} 目录下")

if __name__ == "__main__":
    main()
