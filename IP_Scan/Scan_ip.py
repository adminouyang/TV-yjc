from threading import Thread
import os
import time
import datetime
from datetime import timezone, timedelta
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
                if line and not line.startswith("#"):
                    print(f"解析第{line_num}行: {line}")
                    if ":" in line:
                        ip_part, port = line.split(':', 1)
                        a, b, c, d = ip_part.split('.')
                        
                        # 从文件名提取运营商信息来确定option
                        filename = os.path.basename(config_file)
                        if "电信" in filename:
                            option = 0
                        elif "联通" in filename or "移动" in filename:
                            option = 1
                        else:
                            option = 0
                        
                        url_end = "/status" if option >= 10 else "/stat"
                        
                        if option % 10 == 0:  # 扫描D段
                            ip = f"{a}.{b}.{c}.1"
                        else:  # 扫描C段和D段
                            ip = f"{a}.{b}.1.1"
                            
                        ip_configs.append((ip, port, option, url_end))
                        print(f"生成扫描目标: http://{ip}:{port}{url_end} (option={option})")
        return ip_configs
    except Exception as e:
        print(f"读取文件错误: {e}")
        return []

def generate_ip_ports(ip, port, option):
    a, b, c, d = ip.split('.')
    opt = option % 10
    
    print(f"生成IP范围: 基础IP={ip}, 端口={port}, option={opt}")
    
    if opt == 0:  # 扫描D段：x.x.x.1-255
        ip_list = [f"{a}.{b}.{c}.{y}:{port}" for y in range(1, 256)]
        print(f"扫描D段: 共{len(ip_list)}个IP")
        return ip_list
    
    elif opt == 1:  # 扫描C段和D段
        c_val = int(c)
        if c_val < 255:
            ip_list = ([f"{a}.{b}.{c}.{y}:{port}" for y in range(1, 256)] + 
                      [f"{a}.{b}.{c_val+1}.{y}:{port}" for y in range(1, 256)])
            print(f"扫描C段和D段: 共{len(ip_list)}个IP")
            return ip_list
        else:
            ip_list = [f"{a}.{b}.{c}.{y}:{port}" for y in range(1, 256)]
            print(f"扫描D段(边界情况): 共{len(ip_list)}个IP")
            return ip_list
    
    else:
        ip_list = [f"{a}.{b}.{x}.{y}:{port}" for x in range(256) for y in range(1, 256)]
        print(f"扫描整个B段: 共{len(ip_list)}个IP")
        return ip_list

def check_ip_port(ip_port, url_end):    
    try:
        url = f"http://{ip_port}{url_end}"
        resp = requests.get(url, timeout=3)  # 增加超时时间
        resp.raise_for_status()
        if "Multi stream daemon" in resp.text or "udpxy status" in resp.text:
            print(f"✓ 找到有效IP: {url}")
            return ip_port
        else:
            #print(f"× 响应不匹配: {url}")
            return None
    except requests.exceptions.Timeout:
        #print(f"× 超时: {url}")
        return None
    except requests.exceptions.ConnectionError:
        #print(f"× 连接失败: {url}")
        return None
    except Exception as e:
        #print(f"× 错误: {url} - {str(e)}")
        return None

def scan_ip_port(ip, port, option, url_end):
    def show_progress():
        start_time = time.time()
        while checked[0] < len(ip_ports):
            elapsed = time.time() - start_time
            print(f"进度: {checked[0]}/{len(ip_ports)} ({checked[0]/len(ip_ports)*100:.1f}%), 有效: {len(valid_ip_ports)}, 耗时: {elapsed:.1f}秒")
            time.sleep(10)
    
    valid_ip_ports = []
    ip_ports = generate_ip_ports(ip, port, option)
    checked = [0]
    
    if option % 2 == 1:  # 只有大规模扫描才显示进度
        Thread(target=show_progress, daemon=True).start()
    
    max_workers = 100  # 减少线程数避免被封
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_ip_port, ip_port, url_end): ip_port for ip_port in ip_ports}
        for future in as_completed(futures):
            result = future.result()
            if result:
                valid_ip_ports.append(result)
            checked[0] += 1
    
    return valid_ip_ports

def multicast_province(config_file):
    filename = os.path.basename(config_file)
    province = filename.split('.')[0]
    print(f"\n{'='*50}")
    print(f"开始扫描: {province}")
    print(f"{'='*50}")
    
    configs = read_config(config_file)
    if not configs:
        print("没有读取到有效配置")
        return
    
    print(f"读取完成，共需扫描 {len(configs)}组配置")
    all_ip_ports = []
    
    for ip, port, option, url_end in configs:
        print(f"\n开始扫描: http://{ip}:{port}{url_end}")
        valid_ips = scan_ip_port(ip, port, option, url_end)
        all_ip_ports.extend(valid_ips)
        print(f"本组扫描完成，找到 {len(valid_ips)} 个有效IP")
    
    if all_ip_ports:
        all_ip_ports = sorted(set(all_ip_ports))
        print(f"\n✓ {province} 扫描完成，共找到 {len(all_ip_ports)} 个有效IP")
        
        # 保存结果
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
            print(f"已生成组播文件: 组播_{province}.txt")
        else:
            print(f"缺少模板文件: {template_file}")
    else:
        print(f"\n× {province} 扫描完成，未找到有效IP")

def txt_to_m3u(input_file, output_file):
    try:
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
        print(f"已生成M3U文件: {output_file}")
    except Exception as e:
        print(f"生成M3U文件错误: {e}")

def main():
    # 创建必要的目录
    os.makedirs('ip', exist_ok=True)
    
    # 查找配置文件
    config_files = []
    for file in glob.glob(os.path.join('ip', '*.txt')):
        filename = os.path.basename(file)
        if not filename.endswith('_ip.txt'):
            config_files.append(file)
    
    if not config_files:
        print("未找到配置文件，请在ip文件夹下创建.txt配置文件")
        return
    
    print(f"找到 {len(config_files)} 个配置文件")
    
    for config_file in config_files:
        multicast_province(config_file)
    
    # 合并结果
    file_contents = []
    for pattern in ['组播_*移动.txt', '组播_*电信.txt', '组播_*联通.txt']:
        for file_path in glob.glob(pattern):
            try:
                with open(file_path, 'r', encoding="utf-8") as f:
                    content = f.read()
                    file_contents.append(content)
                print(f"已合并: {file_path}")
            except:
                pass
    
    # 生成时间
    try:
        now = datetime.datetime.now(timezone.utc) + timedelta(hours=8)
    except:
        now = datetime.datetime.utcnow() + timedelta(hours=8)
    current_time = now.strftime("%Y/%m/%d %H:%M")
    
    # 写入总文件
    with open("zubo_all.txt", "w", encoding="utf-8") as f:
        f.write(f"{current_time}更新,#genre#\n")
        f.write(f"浙江卫视,http://ali-m-l.cztv.com/channels/lantian/channel001/1080p.m3u8\n")
        if file_contents:
            f.write('\n'.join(file_contents))
        else:
            f.write("# 暂无有效组播源\n")
    
    txt_to_m3u("zubo_all.txt", "zubo_all.m3u")
    print(f"\n✓ 组播地址获取完成")

if __name__ == "__main__":
    main()
