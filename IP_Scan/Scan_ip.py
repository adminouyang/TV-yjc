from threading import Thread
import os
import time
import datetime
import glob
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

def read_config(config_file):
    print(f"读取设置文件：{config_file}")
    ip_configs = []
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith("#"):  # 跳过空行和注释行
                    # 从文件名提取运营商信息来确定option
                    filename = os.path.basename(config_file)
                    if "电信" in filename:
                        option = 1  # 电信使用option=1（扫描D段）
                    elif "联通" in filename or "移动" in filename:
                        option = 0  # 联通/移动使用option=0（扫描C段和D段）
                    else:
                        option = 1  # 默认使用option=0
                    
                    # 解析IP和端口
                    if ":" in line:
                        ip_part, port = line.split(':', 1)
                        a, b, c, d = ip_part.split('.')
                        url_end = "/status" if option >= 10 else "/stat"
                        
                        # 根据option选择IP生成方式
                        if option % 10 == 1:  # 扫描D段
                            ip = f"{a}.{b}.{c}.1"
                        else:  # 扫描C段和D段
                            ip = f"{a}.{b}.1.1"
                            
                        ip_configs.append((ip, port, option, url_end))
                        print(f"第{line_num}行：http://{ip}:{port}{url_end} 添加到扫描列表 (option={option})")
        return ip_configs
    except Exception as e:
        print(f"读取文件错误: {e}")

def generate_ip_ports(ip, port, option):
    a, b, c, d = ip.split('.')
    opt = option % 10  # 获取option的个位数
    
    if opt == 0:  # 扫描D段：x.x.x.1-255
        return [f"{a}.{b}.{c}.{y}:{port}" for y in range(1, 256)]
    
    elif opt == 1:  # 扫描C段和D段：x.x.x.1-255 和 x.x.x+1.1-255
        c_val = int(c)
        if c_val < 255:  # 确保不超过255
            return ([f"{a}.{b}.{c}.{y}:{port}" for y in range(1, 256)] + 
                    [f"{a}.{b}.{c_val+1}.{y}:{port}" for y in range(1, 256)])
        else:
            return [f"{a}.{b}.{c}.{y}:{port}" for y in range(1, 256)]
    
    elif opt == 2:  # 保留原有的范围扫描功能
        c_extent = c.split('-')
        c_first = int(c_extent[0]) if len(c_extent) == 2 else int(c)
        c_last = int(c_extent[1]) + 1 if len(c_extent) == 2 else int(c) + 8
        return [f"{a}.{b}.{x}.{y}:{port}" for x in range(c_first, c_last) for y in range(1, 256)]
    
    else:  # 默认扫描整个B段
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
    province = filename.split('.')[0]  # 使用文件名作为省份名（去掉.txt扩展名）
    print(f"{'='*25}\n   获取: {province} IP\n{'='*25}")
    configs = sorted(set(read_config(config_file)))
    print(f"读取完成，共需扫描 {len(configs)}组")
    all_ip_ports = []
    
    for ip, port, option, url_end in configs:
        print(f"\n开始扫描  http://{ip}:{port}{url_end}")
        all_ip_ports.extend(scan_ip_port(ip, port, option, url_end))
    
    if len(all_ip_ports) != 0:
        all_ip_ports = sorted(set(all_ip_ports))
        print(f"\n{province} 扫描完成，获取有效ip_port共：{len(all_ip_ports)}个\n{all_ip_ports}\n")
        
        # 保存结果到ip文件夹
        with open(f"ip/{province}_ip.txt", 'w', encoding='utf-8') as f:
            f.write('\n'.join(all_ip_ports))
        
        # 生成组播文件
        template_file = os.path.join('template', f"template_{province}.txt")
        if os.path.exists(template_file):
            with open(template_file, 'r', encoding='utf-8') as f:
                tem_channels = f.read()
            output = [] 
            with open(f"ip/{province}_ip.txt", 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    ip = line.strip()
                    output.append(f"{province}-组播{line_num},#genre#\n")
                    output.append(tem_channels.replace("ipipip", f"{ip}"))
            with open(f"组播_{province}.txt", 'w', encoding='utf-8') as f:
                f.writelines(output)
        else:
            print(f"缺少模板文件: {template_file}")
    else:
        print(f"\n{province} 扫描完成，未扫描到有效ip_port")

def txt_to_m3u(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    with open(output_file, 'w', encoding='utf-8') as f:
        genre = ''
        for line in lines:
            line = line.strip()
            if "," in line:
                channel_name, channel_url = line.split(',', 1)
                if channel_url == '#genre#':
                    genre = channel_name
                else:
                    f.write(f'#EXTINF:-1 group-title="{genre}",{channel_name}\n')
                    f.write(f'{channel_url}\n')

def main():
    # 读取ip文件夹下的所有.txt文件（除了已生成的_ip.txt文件）
    config_files = []
    for file in glob.glob(os.path.join('ip', '*.txt')):
        filename = os.path.basename(file)
        # 跳过已生成的结果文件
        if not filename.endswith('_ip.txt'):
            config_files.append(file)
    
    for config_file in config_files:
        multicast_province(config_file)
    
    # 合并所有组播文件
    file_contents = []
    for file_path in glob.glob('组播_*.txt'):
        with open(file_path, 'r', encoding="utf-8") as f:
            content = f.read()
            file_contents.append(content)
    
    now = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=8)
    current_time = now.strftime("%Y/%m/%d %H:%M")
    
    with open("zubo_all.txt", "w", encoding="utf-8") as f:
        f.write(f"{current_time}更新,#genre#\n")
        f.write(f"浙江卫视,http://ali-m-l.cztv.com/channels/lantian/channel001/1080p.m3u8\n")
        f.write('\n'.join(file_contents))
    
    txt_to_m3u("zubo_all.txt", "zubo_all.m3u")
    print(f"组播地址获取完成")

if __name__ == "__main__":
    main()
