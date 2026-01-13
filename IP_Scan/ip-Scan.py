from threading import Thread
import os
import time
import glob
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

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
                    
                ip_part, port = ip_part_port.split(':')
                ip_parts = ip_part.split('.')
                if len(ip_parts) != 4:
                    print(f"第{line_num}行格式错误: IP地址格式不正确 - {line}")
                    continue
                
                a, b, c, d = ip_parts
                url_end = "/status" if option >= 10 else "/stat"
                ip = f"{a}.{b}.{c}.1" if option % 2 == 0 else f"{a}.{b}.1.1"
                
                ip_configs.append((ip, port, option, url_end, line_num-1, original_line))
                
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
    """处理配置文件，扫描并清理无效配置"""
    filename = os.path.basename(config_file)
    province_name = os.path.splitext(filename)[0]
    print(f"\n{'='*25}\n   处理: {province_name}\n{'='*25}")
    
    # 读取配置
    configs, original_lines = read_config(config_file)
    if not configs:
        print(f"配置文件 {filename} 中没有有效的配置行")
        return []
    
    # 准备记录哪些行有效
    valid_lines = []
    all_valid_ip_ports = []
    
    # 记录扫描进度
    total_configs = len(configs)
    
    for idx, (ip, port, option, url_end, line_num, original_line) in enumerate(configs, 1):
        print(f"\n[{idx}/{total_configs}] 扫描: {original_line}")
        valid_ips = scan_ip_port(ip, port, option, url_end)
        
        if valid_ips:
            all_valid_ip_ports.extend(valid_ips)
            valid_lines.append(line_num)  # 记录有效行号
            print(f"  找到 {len(valid_ips)} 个有效IP")
        else:
            print(f"  没有找到有效IP，将删除此配置行")
    
    # 清理原配置文件，只保留有效的行
    if valid_lines:
        # 创建新的内容列表，包含注释行和有效的配置行
        new_lines = []
        valid_line_nums = set(valid_lines)
        
        for i, line in enumerate(original_lines):
            # 保留注释行、空行和有效的配置行
            if line.strip() == "" or line.strip().startswith("#") or i in valid_line_nums:
                new_lines.append(line)
        
        # 将清理后的配置写回原文件
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
        print(f"\n已清理配置文件，保留 {len(valid_lines)} 个有效配置")
    # else:
    #     # 如果没有找到任何有效IP，清空文件
    #     with open(config_file, 'w', encoding='utf-8') as f:
    #         f.write("")
    #     print(f"\n没有找到任何有效IP，已清空配置文件")
    
    return all_valid_ip_ports

def main():
    # 确保IP_Scan/ip目录存在
    ip_dir = "IP_Scan/ip"
    if not os.path.exists(ip_dir):
        os.makedirs(ip_dir)
        print(f"创建目录: {ip_dir}")
    
    # 获取ip目录下所有的.txt文件（排除已存在的_good_ip.txt结果文件）
    config_files = []
    for file_path in glob.glob(os.path.join(ip_dir, "*_good_ip.txt")):    #for file_path in glob.glob(os.path.join(ip_dir, "*.txt")):
        filename = os.path.basename(file_path)
        if "_Scan_ip.txt" not in filename:                              #if "_good_ip.txt" not in filename:
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
            result_filename = f"{province_name}_Scan_ip.txt"
            result_path = os.path.join(ip_dir, result_filename)
            
            with open(result_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(valid_ip_ports))
            print(f"{province_name}: 保存 {len(valid_ip_ports)} 个有效IP到 {result_filename}")
        else:
            # 修改：不创建空的_Scan_ip.txt文件
            print(f"{province_name}: 没有找到有效IP，不生成结果文件")
        
        print("-" * 50)
    
    print(f"\nIP地址扫描完成，结果保存在 {ip_dir} 目录下")
    print("注意：原配置文件已自动清理，无效的配置行已被删除")

if __name__ == "__main__":
    main()
