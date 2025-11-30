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

}

# 通用测试流（当城市特定流不可用时使用）
COMMON_TEST_STREAMS = [
    "rtp/225.1.1.1:1234",
    "udp/239.1.1.1:1234",
    "rtp/238.1.1.1:1234",
]

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
    # 精确匹配
    if city_name in CITY_STREAMS:
        return CITY_STREAMS[city_name]
    
    # 模糊匹配（包含关系）
    for key, streams in CITY_STREAMS.items():
        if key in city_name or city_name in key:
            return streams
    
    # 运营商匹配
    if "电信" in city_name:
        for key, streams in CITY_STREAMS.items():
            if "电信" in key:
                return streams
    elif "联通" in city_name:
        for key, streams in CITY_STREAMS.items():
            if "联通" in key:
                return streams
    elif "移动" in city_name:
        for key, streams in CITY_STREAMS.items():
            if "移动" in key:
                return streams
    
    # 返回通用测试流
    return COMMON_TEST_STREAMS

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
                            
                            # 根据option确定扫描范围
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
    """根据option值生成要扫描的IP地址列表"""
    parts = ip.split('.')
    if len(parts) != 4:
        print(f"无效的IP格式: {ip}")
        return []
        
    a, b, c, d = parts
    opt = option % 10  # 只取个位数
    
    print(f"生成IP范围: 基础IP={ip}, 端口={port}, option={opt}")
    
    # 限制扫描范围，避免过大
    if opt == 0:  # 扫描D段：x.x.x.1-254
        # 只扫描部分IP，提高效率
        ip_list = [f"{a}.{b}.{c}.{y}" for y in range(1, 255, 5)]  # 每5个IP扫描一个
        print(f"扫描D段: 共{len(ip_list)}个IP")
    elif opt == 1:  # 扫描C段和D段
        c_val = int(c)
        if c_val < 254:
            ip_list = ([f"{a}.{b}.{c}.{y}" for y in range(1, 255, 5)] + 
                      [f"{a}.{b}.{c_val+1}.{y}" for y in range(1, 255, 5)])
            print(f"扫描C段和D段: 共{len(ip_list)}个IP")
        else:
            ip_list = [f"{a}.{b}.{c}.{y}" for y in range(1, 255, 5)]
            print(f"扫描D段(边界情况): 共{len(ip_list)}个IP")
    elif opt == 2:  # 扫描指定范围的C段
        c_extent = c.split('-')
        if len(c_extent) == 2:
            c_first = int(c_extent[0])
            c_last = int(c_extent[1]) + 1
            ip_list = [f"{a}.{b}.{x}.{y}" for x in range(c_first, c_last, 2) for y in range(1, 255, 5)]
            print(f"扫描C段范围 {c_first}-{c_last-1}: 共{len(ip_list)}个IP")
        else:
            ip_list = [f"{a}.{b}.{c}.{y}" for y in range(1, 255, 5)]
            print(f"扫描D段: 共{len(ip_list)}个IP")
    else:  # 默认扫描整个B段
        # 大幅减少扫描范围
        ip_list = [f"{a}.{b}.{x}.{y}" for x in range(1, 254, 10) for y in range(1, 255, 10)]
        print(f"扫描整个B段: 共{len(ip_list)}个IP")
    
    # 添加端口
    ip_ports = [f"{ip}:{port}" for ip in ip_list]
    return ip_ports

def test_stream_speed(stream_url, timeout=15):
    """测试流媒体速度，返回速度(KB/s)和是否成功"""
    try:
        headers = get_random_headers()
        start_time = time.time()
        
        # 设置更长的超时时间
        response = requests.get(stream_url, headers=headers, timeout=timeout, 
                              verify=False, allow_redirects=True, stream=True)
        
        if response.status_code not in [200, 206]:
            return 0, False
        
        # 读取更多数据用于测速（500KB）
        downloaded = 0
        chunk_size = 100 * 1024  # 64KB chunks
        max_download = 1000 * 1024  # 500KB
        
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

def check_single_url(ip_port, province, timeout=15):
    """检查单个URL，直接测试组播流速度"""
    try:
        # 添加随机延迟，避免请求过于频繁
        time.sleep(random.uniform(0.2, 0.8))
        
        print(f"测试: {ip_port} - {province}")
        
        # 获取该城市对应的测试流
        test_streams = get_test_streams_for_city(province)
        print(f"使用测试流: {test_streams}")
        
        best_speed = 0
        best_stream = ""
        
        for stream_path in test_streams:
            stream_url = f"http://{ip_port}/{stream_path}"
            try:
                speed, success = test_stream_speed(stream_url, timeout)
                
                if success:
                    print(f"✓ 流媒体可用: {stream_url} - 速度: {speed:.2f} KB/s")
                    if speed > best_speed:
                        best_speed = speed
                        best_stream = stream_path
                else:
                    #print(f"× 流媒体不可用: {stream_url}")
                    
            except Exception as e:
                #print(f"× 流媒体错误: {stream_url} - {str(e)}")
        
        # 只有速度大于100KB/s才认为是有效的
        if best_speed > 100:
            print(f"✓ 验证通过: {ip_port} - 最佳速度: {best_speed:.2f} KB/s")
            return ip_port, best_speed, best_stream
        else:
            if best_speed > 0:
                print(f"× 速度不足: {ip_port} - 最佳速度: {best_speed:.2f} KB/s")
            else:
                #print(f"× 无响应: {ip_port}")
            return None, 0, ""
        
    except Exception as e:
        #print(f"× 检查过程出错: {ip_port} - {str(e)}")
        return None, 0, ""

def scan_ip_port(ip, port, option, province):
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
    
    # 进一步降低并发数，提高稳定性
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
    return valid_results

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
    all_results = []  # 存储所有有效结果
    
    for ip, port, option in configs:
        print(f"\n开始扫描: {ip}:{port} (option={option})")
        results = scan_ip_port(ip, port, option, province)
        all_results.extend(results)
        print(f"本组扫描完成，找到 {len(results)} 个有效IP")
        
        # 每组扫描后休息一下
        time.sleep(5)
    
    if all_results:
        # 按速度排序
        all_results.sort(key=lambda x: x[1], reverse=True)
        
        # 去重（相同的IP只保留速度最快的）
        unique_results = {}
        for ip_port, speed, stream in all_results:
            if ip_port not in unique_results or speed > unique_results[ip_port][1]:
                unique_results[ip_port] = (ip_port, speed, stream)
        
        unique_results = list(unique_results.values())
        unique_results.sort(key=lambda x: x[1], reverse=True)
        
        print(f"\n✓ {province} 扫描完成，共找到 {len(unique_results)} 个有效IP")
        
        # 保存结果（包含速度信息）
        os.makedirs('ip', exist_ok=True)
        with open(f"ip/{province}_ip.txt", 'w', encoding='utf-8') as f:
            for ip_port, speed, stream in unique_results:
                f.write(f"{ip_port}\n,{speed:.2f} KB/s\n")             #f.write(f"{ip_port},{speed:.2f},{stream}\n")
        
        # 生成组播文件（只包含IP:端口）
        template_file = os.path.join('template', f"template_{province}.txt")
        if os.path.exists(template_file):
            with open(template_file, 'r', encoding='utf-8') as f:
                tem_channels = f.read()
            output = []
            for i, (ip_port, speed, stream) in enumerate(unique_results, 1):
                output.append(f"{province}-组播{i}({speed:.0f}KB/s),#genre#\n")
                output.append(tem_channels.replace("ipipip", f"{ip_port}"))
            
            os.makedirs('my_tv', exist_ok=True)
            with open(f"my_tv/组播_{province}.txt", 'w', encoding='utf-8') as f:
                f.writelines(output)
            print(f"已生成组播文件: my_tv/组播_{province}.txt")
        else:
            print(f"缺少模板文件: {template_file}")
            
        # 显示速度统计
        speeds = [speed for _, speed, _ in unique_results]
        if speeds:
            avg_speed = sum(speeds) / len(speeds)
            max_speed = max(speeds)
            min_speed = min(speeds)
            print(f"速度统计: 平均{avg_speed:.2f}KB/s, 最高{max_speed:.2f}KB/s, 最低{min_speed:.2f}KB/s")
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
        example_content = """# 示例配置文件
# 格式: IP:端口 (默认option=0)
# 或者: IP:端口,option (指定option值)

# 扫描D段 (option=0)
114.107.2.156:2000

# 扫描C段和D段 (option=1)  
114.107.2.156:2000,1

# 扫描指定C段范围 (option=2)
114.107.2-10.156:2000,2

# 扫描整个B段 (option=3)
114.107.2.156:2000,3
"""
        with open(os.path.join(ip_dir, '示例电信.txt'), 'w', encoding='utf-8') as f:
            f.write(example_content)
        print("已创建示例配置文件: ip/示例电信.txt")
        return
    
    print(f"找到 {len(config_files)} 个配置文件: {[os.path.basename(f) for f in config_files]}")
    
    for config_file in config_files:
        multicast_province(config_file)
        # 每组扫描后休息更长时间
        time.sleep(10)
    
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
