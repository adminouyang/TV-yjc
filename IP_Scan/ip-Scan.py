from threading import Thread
import os
import time
import glob
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

def read_config(config_file):
    print(f"读取设置文件：{config_file}")
    ip_configs = []
    try:
        with open(config_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
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
                        
                    ip_part, port = ip_part_port.split(':')
                    ip_parts = ip_part.split('.')
                    if len(ip_parts) != 4:
                        print(f"第{line_num}行格式错误: IP地址格式不正确 - {line}")
                        continue
                    
                    a, b, c, d = ip_parts
                    url_end = "/status" if option >= 10 else "/stat"
                    ip = f"{a}.{b}.{c}.1" if option % 2 == 0 else f"{a}.{b}.1.1"
                    
                    ip_configs.append((ip, port, option, url_end, line))
                    
                except Exception as e:
                    print(f"第{line_num}行格式错误: {e} - {line}")
                    continue
                    
        return ip_configs
    except Exception as e:
        print(f"读取文件错误: {e}")
        return []

def generate_ip_ports(ip, port, option):
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
    try:
        url = f"http://{ip_port}{url_end}"
        resp = requests.get(url, timeout=2)
        resp.raise_for_status()
        if "Multi stream daemon" in resp.text or "udpxy status" in resp.text:
            return ip_port
    except:
        return None

def scan_ip_port(ip, port, option, url_end):
    def show_progress():
        while checked[0] < len(ip_ports) and option % 2 == 1:
            time.sleep(30)
    
    valid_ip_ports = []
    ip_ports = generate_ip_ports(ip, port, option)
    checked = [0]
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
    filename = os.path.basename(config_file)
    province_name = os.path.splitext(filename)[0]
    print(f"\n{'='*25}\n   获取: {province_name}ip_port\n{'='*25}")
    
    configs = read_config(config_file)
    if not configs:
        print(f"配置文件 {filename} 中没有有效的配置行，跳过扫描")
        return []
    
    all_valid_ip_ports = []
    
    for ip, port, option, url_end, original_line in configs:
        print(f"扫描: {original_line}")
        valid_ips = scan_ip_port(ip, port, option, url_end)
        
        if valid_ips:
            all_valid_ip_ports.extend(valid_ips)
            print(f"找到 {len(valid_ips)} 个有效IP")
        else:
            print(f"没有找到有效IP")
    
    return all_valid_ip_ports

def main():
    # 确保IP_Scan/ip目录存在
    ip_dir = "IP_Scan/ip"
    if not os.path.exists(ip_dir):
        os.makedirs(ip_dir)
        print(f"创建目录: {ip_dir}")
    
    # 获取ip目录下所有的.txt文件（排除已存在的_good_ip.txt结果文件）
    config_files = []
    for file_path in glob.glob(os.path.join(ip_dir, "*.txt")):
        filename = os.path.basename(file_path)
        if "_good_ip.txt" not in filename:
            config_files.append(file_path)
    
    if not config_files:
        print(f"在 '{ip_dir}' 目录下未找到配置文件")
        return
    
    print(f"找到 {len(config_files)} 个配置文件")
    
    # 处理所有配置文件
    for config_file in config_files:
        filename = os.path.basename(config_file)
        province_name = os.path.splitext(filename)[0]
        
        valid_ip_ports = process_config_file(config_file)
        
        if valid_ip_ports:
            valid_ip_ports = sorted(set(valid_ip_ports))
            result_filename = f"{province_name}_good_ip.txt"
            result_path = os.path.join(ip_dir, result_filename)
            
            with open(result_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(valid_ip_ports))
            print(f"{province_name}: 保存 {len(valid_ip_ports)} 个有效IP到 {result_filename}")
        else:
            print(f"{province_name}: 未找到有效IP")
    
    print(f"\nIP地址扫描完成，结果保存在 {ip_dir} 目录下")

if __name__ == "__main__":
    main()
