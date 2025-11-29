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

def get_random_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }

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
                        parts = ip_part.split('.')
                        if len(parts) == 4:
                            a, b, c, d = parts
                            
                            # 从文件名提取运营商信息来确定option
                            filename = os.path.basename(config_file)
                            if "电信" in filename:
                                option = 0
                            elif "联通" in filename or "移动" in filename:
                                option = 1
                            else:
                                option = 0
                            
                            if option % 10 == 0:  # 扫描D段
                                ip = f"{a}.{b}.{c}.1"
                            else:  # 扫描C段和D段
                                ip = f"{a}.{b}.1.1"
                                
                            ip_configs.append((ip, port, option))
                            print(f"生成扫描目标: {ip}:{port} (option={option})")
        return ip_configs
    except Exception as e:
        print(f"读取文件错误: {e}")
        return []

def generate_ip_ports(ip, port, option):
    parts = ip.split('.')
    if len(parts) != 4:
        print(f"无效的IP格式: {ip}")
        return []
        
    a, b, c, d = parts
    opt = option % 10
    
    print(f"生成IP范围: 基础IP={ip}, 端口={port}, option={opt}")
    
    # 限制扫描范围，避免过大
    if opt == 0:  # 扫描D段：x.x.x.1-254
        ip_list = [f"{a}.{b}.{c}.{y}" for y in range(1, 255)]
        print(f"扫描D段: 共{len(ip_list)}个IP")
    elif opt == 1:  # 扫描C段和D段
        c_val = int(c)
        if c_val < 254:
            ip_list = ([f"{a}.{b}.{c}.{y}" for y in range(1, 255)] + 
                      [f"{a}.{b}.{c_val+1}.{y}" for y in range(1, 255)])
            print(f"扫描C段和D段: 共{len(ip_list)}个IP")
        else:
            ip_list = [f"{a}.{b}.{c}.{y}" for y in range(1, 255)]
            print(f"扫描D段(边界情况): 共{len(ip_list)}个IP")
    else:
        # 限制B段扫描范围，避免过大
        ip_list = [f"{a}.{b}.{x}.{y}" for x in range(1, 254) for y in range(1, 255)]
        print(f"扫描整个B段: 共{len(ip_list)}个IP")
    
    # 添加端口
    ip_ports = [f"{ip}:{port}" for ip in ip_list]
    return ip_ports

def check_single_url(url, timeout=8):
    """检查单个URL"""
    try:
        headers = get_random_headers()
        
        # 添加随机延迟，避免请求过于频繁
        time.sleep(random.uniform(0.1, 0.5))
        
        # 尝试多种路径
        paths_to_try = [
            "/status",
            "/stat",
            "/udpxy",
            "/"
        ]
        
        for path in paths_to_try:
            test_url = f"http://{url}{path}"
            try:
                print(f"测试: {test_url}")
                resp = requests.get(test_url, headers=headers, timeout=timeout, 
                                  verify=False, allow_redirects=True)
                
                if resp.status_code == 200:
                    content = resp.text.lower()
                    # 检查常见的关键词
                    if any(keyword in content for keyword in ['udpxy', 'multi stream', 'status']):
                        print(f"✓ 找到有效服务: {test_url}")
                        return url
                    else:
                        print(f"× 响应内容不匹配: {test_url}")
                else:
                    print(f"× HTTP状态码 {resp.status_code}: {test_url}")
                    
            except requests.exceptions.Timeout:
                print(f"× 超时: {test_url}")
            except requests.exceptions.ConnectionError:
                print(f"× 连接失败: {test_url}")
            except Exception as e:
                print(f"× 错误: {test_url} - {str(e)}")
                
        return None
        
    except Exception as e:
        print(f"× 检查过程出错: {url} - {str(e)}")
        return None

def scan_ip_port(ip, port, option):
    def show_progress():
        start_time = time.time()
        while checked[0] < len(ip_ports):
            elapsed = time.time() - start_time
            rate = checked[0] / elapsed if elapsed > 0 else 0
            print(f"进度: {checked[0]}/{len(ip_ports)} ({checked[0]/len(ip_ports)*100:.1f}%), "
                  f"有效: {len(valid_ip_ports)}, 速率: {rate:.1f}个/秒, 耗时: {elapsed:.1f}秒")
            time.sleep(10)
    
    valid_ip_ports = []
    ip_ports = generate_ip_ports(ip, port, option)
    
    if not ip_ports:
        print("没有生成有效的IP列表")
        return []
    
    checked = [0]
    
    # 显示进度
    Thread(target=show_progress, daemon=True).start()
    
    # 减少并发数，避免被封锁
    max_workers = 20
    print(f"开始扫描，使用 {max_workers} 个线程")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_single_url, ip_port): ip_port for ip_port in ip_ports}
        
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
    
    for ip, port, option in configs:
        print(f"\n开始扫描: {ip}:{port}")
        valid_ips = scan_ip_port(ip, port, option)
        all_ip_ports.extend(valid_ips)
        print(f"本组扫描完成，找到 {len(valid_ips)} 个有效IP")
        
        # 每组扫描后休息一下
        time.sleep(2)
    
    if all_ip_ports:
        all_ip_ports = sorted(set(all_ip_ports))
        print(f"\n✓ {province} 扫描完成，共找到 {len(all_ip_ports)} 个有效IP")
        
        # 保存结果
        os.makedirs('ip', exist_ok=True)
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
                    ip_port = line.strip()
                    output.append(f"{province}-组播{line_num},#genre#\n")
                    output.append(tem_channels.replace("ipipip", f"{ip_port}"))
            
            os.makedirs('my_tv', exist_ok=True)
            with open(f"my_tv/组播_{province}.txt", 'w', encoding='utf-8') as f:
                f.writelines(output)
            print(f"已生成组播文件: my_tv/组播_{province}.txt")
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
    print("开始扫描组播源...")
    
    # 创建必要的目录
    os.makedirs('ip', exist_ok=True)
    os.makedirs('template', exist_ok=True)
    os.makedirs('my_tv', exist_ok=True)
    
    # 查找配置文件
    config_files = []
    ip_dir = 'ip'
    if os.path.exists(ip_dir):
        for file in glob.glob(os.path.join(ip_dir, '*.txt')):
            filename = os.path.basename(file)
            if not filename.endswith('_ip.txt'):
                config_files.append(file)
    
    if not config_files:
        print("未找到配置文件，请在ip文件夹下创建.txt配置文件")
        # 创建示例配置文件
        example_content = "# 示例配置文件\n# 格式: IP:端口\n192.168.1.1:4022\n10.0.0.1:8080"
        with open(os.path.join(ip_dir, '示例电信.txt'), 'w', encoding='utf-8') as f:
            f.write(example_content)
        print("已创建示例配置文件: ip/示例电信.txt")
        return
    
    print(f"找到 {len(config_files)} 个配置文件: {[os.path.basename(f) for f in config_files]}")
    
    for config_file in config_files:
        multicast_province(config_file)
        # 每组扫描后休息更长时间
        time.sleep(5)
    
    # 合并结果
    file_contents = []
    my_tv_dir = 'my_tv'
    if os.path.exists(my_tv_dir):
        for pattern in ['组播_*移动.txt', '组播_*电信.txt', '组播_*联通.txt', '组播_*.txt']:
            for file_path in glob.glob(os.path.join(my_tv_dir, pattern)):
                try:
                    with open(file_path, 'r', encoding="utf-8") as f:
                        content = f.read()
                        file_contents.append(content)
                    print(f"已合并: {file_path}")
                except Exception as e:
                    print(f"合并文件出错 {file_path}: {e}")
    
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
            for content in file_contents:
                f.write(content)
                f.write('\n')
        else:
            f.write("# 暂无有效组播源\n")
    
    txt_to_m3u("zubo_all.txt", "zubo_all.m3u")
    print(f"\n✓ 组播地址获取完成")

if __name__ == "__main__":
    main()
