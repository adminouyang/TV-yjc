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
                        # 格式: IP:端口,选项
                        parts = line.split(',')
                        ip_part_port = parts[0].strip()
                        option = int(parts[1])
                    else:
                        # 格式: IP:端口 (默认选项为12)
                        ip_part_port = line.strip()
                        option = 12
                    
                    # 解析IP和端口
                    if ":" not in ip_part_port:
                        print(f"第{line_num}行格式错误: 缺少端口号 - {line}")
                        continue
                        
                    ip_part, port = ip_part_port.split(':')
                    
                    # 验证IP格式
                    ip_parts = ip_part.split('.')
                    if len(ip_parts) != 4:
                        print(f"第{line_num}行格式错误: IP地址格式不正确 - {line}")
                        continue
                    
                    a, b, c, d = ip_parts
                    
                    # 计算URL后缀和基础IP
                    url_end = "/status" if option >= 10 else "/stat"
                    ip = f"{a}.{b}.{c}.1" if option % 2 == 0 else f"{a}.{b}.1.1"
                    
                    ip_configs.append((ip, port, option, url_end))
                    print(f"第{line_num}行：http://{ip}:{port}{url_end}添加到扫描列表")
                    
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

# 发送get请求检测url是否可访问        
def check_ip_port(ip_port, url_end):    
    try:
        url = f"http://{ip_port}{url_end}"
        resp = requests.get(url, timeout=2)
        resp.raise_for_status()
        if "Multi stream daemon" in resp.text or "udpxy status" in resp.text:
            print(f"{url} 访问成功")
            return ip_port
    except:
        return None

# 多线程检测url，获取有效ip_port
def scan_ip_port(ip, port, option, url_end):
    def show_progress():
        while checked[0] < len(ip_ports) and option % 2 == 1:
            print(f"已扫描：{checked[0]}/{len(ip_ports)}, 有效ip_port：{len(valid_ip_ports)}个")
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

def multicast_province(config_file):
    filename = os.path.basename(config_file)
    # 获取文件名（不带扩展名）作为省份名称
    province_name = os.path.splitext(filename)[0]
    print(f"{'='*25}\n   获取: {province_name}ip_port\n{'='*25}")
    
    # 读取原始配置文件，并过滤可访问的IP
    valid_configs = []
    all_ip_ports = []
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            original_lines = f.readlines()
            
        for line_num, line in enumerate(original_lines, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                # 保留注释和空行
                valid_configs.append(line)
                continue
                
            try:
                if "," in line:
                    # 格式: IP:端口,选项
                    parts = line.split(',')
                    ip_part_port = parts[0].strip()
                    option = int(parts[1])
                else:
                    # 格式: IP:端口 (默认选项为12)
                    ip_part_port = line.strip()
                    option = 12
                
                # 解析IP和端口
                if ":" not in ip_part_port:
                    print(f"第{line_num}行格式错误: 缺少端口号 - {line}")
                    continue
                    
                original_ip, port = ip_part_port.split(':')
                
                # 验证IP格式
                ip_parts = original_ip.split('.')
                if len(ip_parts) != 4:
                    print(f"第{line_num}行格式错误: IP地址格式不正确 - {line}")
                    continue
                
                a, b, c, d = ip_parts
                
                # 计算URL后缀和基础IP
                url_end = "/status" if option >= 10 else "/stat"
                ip = f"{a}.{b}.{c}.1" if option % 2 == 0 else f"{a}.{b}.1.1"
                
                # 扫描这个配置
                print(f"\n开始扫描: {line}")
                valid_ips = scan_ip_port(ip, port, option, url_end)
                
                if valid_ips:
                    # 找到有效的IP，保留这个配置
                    valid_configs.append(line)
                    all_ip_ports.extend(valid_ips)
                    print(f"第{line_num}行找到 {len(valid_ips)} 个有效IP")
                else:
                    print(f"第{line_num}行没有找到有效IP，将从配置文件中删除")
                    
            except Exception as e:
                print(f"第{line_num}行处理错误: {e} - {line}")
                # 如果解析错误，保留原行
                valid_configs.append(line)
                continue
                
    except Exception as e:
        print(f"读取配置文件错误: {e}")
        return
    
    if len(all_ip_ports) != 0:
        all_ip_ports = sorted(set(all_ip_ports))
        print(f"\n{province_name} 扫描完成，获取有效ip_port共：{len(all_ip_ports)}个\n")
        
        # 1. 保存扫描结果，文件名格式为：原文件名_good_ip.txt
        result_filename = f"{province_name}_good_ip.txt"
        result_path = os.path.join("IP_Scan", "ip", result_filename)
        
        with open(result_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(all_ip_ports))
        print(f"扫描结果已保存到: {result_path}")
        
        # 2. 更新原配置文件，只保留可访问的IP
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(valid_configs))
        print(f"配置文件已更新，只保留可访问的IP配置")
    else:
        print(f"\n{province_name} 扫描完成，未扫描到有效ip_port")
        # 清空原配置文件
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write('')

def main():
    # 确保IP_Scan/ip目录存在
    ip_dir = os.path.join("IP_Scan", "ip")
    if not os.path.exists(ip_dir):
        print(f"错误：目录 '{ip_dir}' 不存在！")
        return
    
    # 获取IP_Scan/ip目录下所有的.txt文件（排除已存在的_good_ip.txt结果文件）
    config_files = []
    for file_path in glob.glob(os.path.join(ip_dir, "*.txt")):
        filename = os.path.basename(file_path)
        # 跳过已经是结果文件的_good_ip.txt
        if "_good_ip.txt" not in filename:
            config_files.append(file_path)
    
    if not config_files:
        print(f"在 '{ip_dir}' 目录下未找到配置文件")
        return
    
    print(f"找到 {len(config_files)} 个配置文件")
    
    # 遍历所有配置文件并扫描
    for config_file in config_files:
        multicast_province(config_file)
    
    print(f"\nIP地址扫描完成，结果保存在 {ip_dir} 目录下")

if __name__ == "__main__":
    main()
