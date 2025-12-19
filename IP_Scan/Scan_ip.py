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

# 分类排序顺序
CATEGORY_ORDER = [
    "央视频道",
    "卫视频道", 
    "数字频道",
    "港澳台频道",
    "安徽频道",
    "北京频道",
    "江苏频道",
    "四川频道",
    "其它频道"
]

# 央视频道顺序
CCTV_ORDER = [
    "CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV5", "CCTV5+", "CCTV6", "CCTV7", 
    "CCTV8", "CCTV9", "CCTV10", "CCTV11", "CCTV12", "CCTV13", "CCTV14", 
    "CCTV15", "CCTV16", "CCTV17", "CCTV4K", "CCTV8K", "CCTV戏曲", "CCTV音乐"
]

# 拼音映射字典（卫视频道常用字）
PINYIN_MAP = {
    '安': 'A', '北': 'B', '重': 'C', '大': 'D', '东': 'D', '福': 'F', '广': 'G', '贵': 'G',
    '海': 'H', '河': 'H', '黑': 'H', '湖': 'H', '吉': 'J', '江': 'J', '金': 'J', '辽': 'L',
    '内': 'N', '宁': 'N', '青': 'Q', '山': 'S', '陕': 'S', '上': 'S', '四': 'S', '天': 'T',
    '西': 'X', '厦': 'X', '新': 'X', '云': 'Y', '浙': 'Z', '中': 'Z'
}

def get_pinyin_first_char(channel_name):
    """获取频道名称第一个汉字的拼音首字母"""
    if not channel_name:
        return 'Z'  # 默认放在最后
    
    first_char = channel_name[0]
    return PINYIN_MAP.get(first_char, first_char)

def sort_channels_by_category(category_name, channel_names):
    """根据分类名称对频道进行排序"""
    if category_name == "央视频道":
        # 按照CCTV_ORDER中的顺序排序
        sorted_channels = []
        for cctv in CCTV_ORDER:
            if cctv in channel_names:
                sorted_channels.append(cctv)
        
        # 添加不在列表中的CCTV频道
        for channel in channel_names:
            if channel.startswith("CCTV") and channel not in sorted_channels:
                sorted_channels.append(channel)
        
        # 添加非CCTV频道
        for channel in channel_names:
            if not channel.startswith("CCTV"):
                sorted_channels.append(channel)
                
        return sorted_channels
    
    elif category_name == "卫视频道":
        # 按照第一个汉字的拼音首字母排序
        return sorted(channel_names, key=lambda x: get_pinyin_first_char(x))
    
    else:
        # 其他分类按字母顺序排序
        return sorted(channel_names)

def get_random_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
        'Range': 'bytes=0-',
    }

def read_config(config_file, city_name):
    """读取配置文件，返回IP列表和option值"""
    print(f"读取配置文件: {config_file}")
    ip_configs = []
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith("#"):
                    # 解析IP:端口和可选的option值
                    if "," in line:
                        parts = line.split(',', 1)
                        ip_port = parts[0].strip()
                        option = int(parts[1].strip()) if parts[1].strip().isdigit() else 0
                    else:
                        ip_port = line
                        option = 0
                    
                    ip_configs.append((ip_port, option))
        
        print(f"读取到 {len(ip_configs)} 个IP配置")
        return ip_configs
    except Exception as e:
        print(f"读取文件错误: {e}")
        return []

def test_stream_speed(stream_url, timeout=5):
    """测试流媒体速度，返回速度(KB/s)和是否成功"""
    try:
        headers = get_random_headers()
        start_time = time.time()
        
        response = requests.get(stream_url, headers=headers, timeout=timeout, 
                              verify=False, allow_redirects=True, stream=True)
        
        if response.status_code not in [200, 206]:
            return 0, False
        
        # 读取100KB数据用于测速
        downloaded = 0
        chunk_size = 10 * 1024  # 10KB chunks
        max_download = 100 * 1024  # 100KB
        
        for chunk in response.iter_content(chunk_size=chunk_size):
            downloaded += len(chunk)
            if downloaded >= max_download:
                break
        
        end_time = time.time()
        duration = end_time - start_time
        
        if duration > 0:
            speed_kbs = downloaded / duration / 1024
            return speed_kbs, True
        else:
            return 0, False
            
    except Exception as e:
        return 0, False

def test_ip_single(ip_port, city_name, timeout=5):
    """测试单个IP，返回速度"""
    if city_name not in CITY_STREAMS:
        return None, 0
    
    test_stream = CITY_STREAMS[city_name][0]  # 只使用第一个测试流
    stream_url = f"http://{ip_port}/{test_stream}"
    
    try:
        time.sleep(random.uniform(0.1, 0.3))  # 随机延迟
        speed, success = test_stream_speed(stream_url, timeout)
        
        if success and speed > 0:
            print(f"✓ {ip_port} 可用 - 速度: {speed:.2f} KB/s")
            return ip_port, speed
        else:
            print(f"× {ip_port} 不可用或速度过慢")
            return None, 0
    except Exception as e:
        print(f"× {ip_port} 测试出错: {str(e)[:50]}")
        return None, 0

def validate_city_ips(city_name):
    """验证城市IP文件中的IP，删除不可用的，保留可用的"""
    config_file = f"ip/{city_name}.txt"
    if not os.path.exists(config_file):
        print(f"配置文件不存在: {config_file}")
        return []
    
    # 读取配置
    ip_configs = read_config(config_file, city_name)
    if not ip_configs:
        print(f"没有读取到IP配置: {city_name}")
        return []
    
    print(f"\n开始验证 {city_name} 的IP...")
    valid_ips = []
    
    # 使用线程池并发测试
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for ip_port, option in ip_configs:
            future = executor.submit(test_ip_single, ip_port, city_name)
            futures.append(future)
        
        for future in as_completed(futures):
            ip_port, speed = future.result()
            if ip_port:
                valid_ips.append((ip_port, speed))
    
    # 按速度排序
    valid_ips.sort(key=lambda x: x[1], reverse=True)
    
    # 更新原文件（只保留可用的IP）
    with open(config_file, 'w', encoding='utf-8') as f:
        for ip_port, speed in valid_ips:
            f.write(f"{ip_port}\n")
    
    # 写入_ip.txt文件（去重）
    ip_file = f"ip/{city_name}_ip.txt"
    existing_ips = set()
    
    # 读取已存在的IP
    if os.path.exists(ip_file):
        with open(ip_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and ":" in line:
                    existing_ips.add(line.split(',')[0].strip())
    
    # 添加新的可用IP
    with open(ip_file, 'a', encoding='utf-8') as f:
        for ip_port, speed in valid_ips:
            if ip_port not in existing_ips:
                f.write(f"{ip_port}\n")
                existing_ips.add(ip_port)
    
    print(f"\n{city_name} 验证完成:")
    print(f"  - 原文件保留: {len(valid_ips)} 个可用IP")
    print(f"  - {city_name}_ip.txt 文件已更新")
    
    return valid_ips

def generate_ip_ports(ip_port, option):
    """根据option值生成要扫描的IP地址列表"""
    ip, port = ip_port.split(':')
    parts = ip.split('.')
    if len(parts) != 4:
        print(f"无效的IP格式: {ip}")
        return []
    
    a, b, c, d = parts
    opt = option % 10
    
    print(f"生成IP范围: 基础IP={ip}:{port}, option={opt}")
    
    # 根据option值生成不同的IP范围
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
    elif opt == 2:  # 扫描指定范围的C段
        c_extent = c.split('-')
        if len(c_extent) == 2:
            c_first = int(c_extent[0])
            c_last = int(c_extent[1]) + 1
            ip_list = [f"{a}.{b}.{x}.{y}" for x in range(c_first, c_last) for y in range(1, 255)]
            print(f"扫描C段范围 {c_first}-{c_last-1}: 共{len(ip_list)}个IP")
        else:
            ip_list = [f"{a}.{b}.{c}.{y}" for y in range(1, 255)]
            print(f"扫描D段: 共{len(ip_list)}个IP")
    else:  # 默认扫描整个B段
        ip_list = [f"{a}.{b}.{x}.{y}" for x in range(1, 254) for y in range(1, 255)]
        print(f"扫描整个B段: 共{len(ip_list)}个IP")
    
    # 添加端口
    ip_ports = [f"{ip}:{port}" for ip in ip_list]
    return ip_ports

def scan_ip_range(ip_port, option, city_name):
    """扫描IP范围，返回可用的IP和速度"""
    if city_name not in CITY_STREAMS:
        return []
    
    test_stream = CITY_STREAMS[city_name][0]
    ip_ports = generate_ip_ports(ip_port, option)
    
    if not ip_ports:
        return []
    
    print(f"开始扫描 {city_name} 的IP范围，共 {len(ip_ports)} 个IP")
    valid_ips = []
    checked = 0
    
    def show_progress():
        start_time = time.time()
        while checked < len(ip_ports):
            elapsed = time.time() - start_time
            rate = checked / elapsed if elapsed > 0 else 0
            valid_count = len(valid_ips)
            print(f"进度: {checked}/{len(ip_ports)} ({checked/len(ip_ports)*100:.1f}%), "
                  f"有效: {valid_count}, 速率: {rate:.1f}个/秒, 耗时: {elapsed:.1f}秒")
            time.sleep(5)
    
    # 显示进度
    Thread(target=show_progress, daemon=True).start()
    
    # 并发扫描
    max_workers = 5
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for ip in ip_ports:
            future = executor.submit(test_ip_single, ip, city_name)
            futures[future] = ip
        
        for future in as_completed(futures):
            result_ip, speed = future.result()
            if result_ip:
                valid_ips.append((result_ip, speed))
            checked += 1
    
    # 按速度排序
    valid_ips.sort(key=lambda x: x[1], reverse=True)
    return valid_ips

def get_top_ips_for_city(city_name, top_n=3):
    """获取城市IP列表中的前N名IP"""
    ip_file = f"ip/{city_name}_ip.txt"
    if not os.path.exists(ip_file):
        print(f"IP文件不存在: {ip_file}")
        return []
    
    # 读取IP列表
    ip_configs = []
    with open(ip_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and ":" in line:
                ip_configs.append(line)
    
    if not ip_configs:
        print(f"{city_name} 没有可用的IP")
        return []
    
    print(f"\n开始测试 {city_name} 的 {len(ip_configs)} 个IP...")
    
    all_valid_ips = []
    
    # 首先测试已有的IP
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(test_ip_single, ip, city_name): ip for ip in ip_configs}
        
        for future in as_completed(futures):
            ip, speed = future.result()
            if ip:
                all_valid_ips.append((ip, speed))
    
    # 按速度排序
    all_valid_ips.sort(key=lambda x: x[1], reverse=True)
    
    # 只取前N名
    top_ips = all_valid_ips[:top_n]
    
    print(f"\n{city_name} 测试完成:")
    for i, (ip, speed) in enumerate(top_ips, 1):
        print(f"  第{i}名: {ip} - 速度: {speed:.2f} KB/s")
    
    return top_ips

def read_template_file(city_name):
    """读取城市对应的频道模板文件"""
    template_file = f"template/{city_name}.txt"
    if not os.path.exists(template_file):
        print(f"频道模板文件不存在: {template_file}")
        return None
    
    print(f"读取频道模板: {template_file}")
    
    categories = []  # 存储(分类名称, 频道列表)
    current_category = ""
    current_channels = []
    
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                if ",#genre#" in line:
                    # 如果是分类行
                    if current_category and current_channels:
                        categories.append((current_category, current_channels))
                    
                    current_category = line.replace(",#genre#", "").strip()
                    current_channels = []
                    print(f"  发现分类: {current_category}")
                elif line and "," in line:
                    # 如果是频道行
                    parts = line.split(",", 1)
                    if len(parts) == 2:
                        channel_name = parts[0].strip()
                        channel_url = parts[1].strip()
                        current_channels.append((channel_name, channel_url))
        
        # 添加最后一个分类
        if current_category and current_channels:
            categories.append((current_category, current_channels))
        
        print(f"  共读取到 {len(categories)} 个分类，总计 {sum(len(channels) for _, channels in categories)} 个频道")
        return categories
    except Exception as e:
        print(f"读取模板文件错误: {e}")
        return None

def read_logo_file():
    """读取台标文件"""
    logo_dict = {}
    logo_file = "template/logo.txt"
    
    if os.path.exists(logo_file):
        try:
            with open(logo_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and ',' in line:
                        parts = line.split(',', 1)
                        if len(parts) == 2:
                            channel_name = parts[0].strip()
                            logo_url = parts[1].strip()
                            logo_dict[channel_name] = logo_url
            print(f"读取到 {len(logo_dict)} 个台标")
        except Exception as e:
            print(f"读取台标文件错误: {e}")
    else:
        print(f"台标文件不存在: {logo_file}")
    
    return logo_dict

def generate_files_for_city(city_name, top_ips, logo_dict):
    """为城市生成TXT和M3U文件，使用3个IP生成3套源"""
    if not top_ips or len(top_ips) < 3:
        print(f"{city_name} 可用的IP数量不足3个，跳过文件生成")
        return
    
    # 读取频道模板
    categories = read_template_file(city_name)
    if not categories:
        print(f"{city_name} 没有频道模板，跳过文件生成")
        return
    
    # 创建输出目录
    os.makedirs('output', exist_ok=True)
    
    # 取前3个IP
    top_3_ips = [ip for ip, _ in top_ips[:3]]
    
    # 生成TXT文件
    txt_file = f"output/{city_name}.txt"
    m3u_file = f"output/{city_name}.m3u"
    
    with open(txt_file, 'w', encoding='utf-8') as txt_f, \
         open(m3u_file, 'w', encoding='utf-8') as m3u_f:
        
        m3u_f.write("#EXTM3U\n")
        
        channel_count = 0
        
        for category, channels in categories:
            # 写入分类标题
            txt_f.write(f"{category},#genre#\n")
            
            for channel_name, channel_url in channels:
                # 为每个频道生成3个源，分别使用3个IP
                for i, ip_port in enumerate(top_3_ips, 1):
                    # 替换ipipip为实际IP:端口
                    new_url = channel_url.replace("ipipip", ip_port)
                    
                    # 写入TXT文件 - 格式: 频道名称,URL$城市
                    txt_f.write(f"{channel_name},{new_url}${city_name}\n")
                    
                    # 写入M3U文件
                    # 查找台标
                    logo_url = logo_dict.get(channel_name, "")
                    
                    if logo_url:
                        m3u_f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" tvg-logo="{logo_url}" group-title="{category}",{channel_name}${city_name}\n')
                    else:
                        m3u_f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" group-title="{category}",{channel_name}${city_name}\n')
                    m3u_f.write(f"{new_url}\n")
                    
                    channel_count += 1
        
        print(f"  TXT文件: {txt_file} (共{channel_count}个频道，每个频道{len(top_3_ips)}个源)")
        print(f"  M3U文件: {m3u_file}")
    
    return txt_file, m3u_file

def sort_categories_by_order(categories_dict):
    """按照指定顺序对分类进行排序"""
    sorted_categories = []
    remaining_categories = list(categories_dict.keys())
    
    # 首先按照预定义的顺序排序
    for category in CATEGORY_ORDER:
        if category in categories_dict:
            sorted_categories.append(category)
            remaining_categories.remove(category)
    
    # 剩余的未在顺序列表中的分类按照字母顺序排序
    sorted_categories.extend(sorted(remaining_categories))
    
    return sorted_categories

def merge_all_files():
    """合并所有城市的TXT和M3U文件，相同频道放在一起"""
    txt_files = glob.glob("output/*.txt")
    m3u_files = glob.glob("output/*.m3u")
    
    if not txt_files or not m3u_files:
        print("没有找到输出文件可合并")
        return
    
    # 按城市名称排序
    txt_files.sort()
    m3u_files.sort()
    
    # 读取台标文件
    logo_dict = read_logo_file()
    
    # 生成时间
    try:
        now = datetime.datetime.now(timezone.utc) + timedelta(hours=8)
    except:
        now = datetime.datetime.utcnow() + timedelta(hours=8)
    current_time = now.strftime("%Y/%m/%d %H:%M")
    
    # 收集所有频道
    # 结构: {category: {channel_name: [(url, city), ...]}}
    all_channels_by_category = {}
    
    # 先收集所有频道的源
    for txt_file in txt_files:
        city_name = os.path.basename(txt_file).replace('.txt', '')
        
        with open(txt_file, 'r', encoding='utf-8') as f:
            current_category = ""
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                if ",#genre#" in line:
                    current_category = line.replace(",#genre#", "").strip()
                    if current_category not in all_channels_by_category:
                        all_channels_by_category[current_category] = {}
                elif line and "," in line and current_category:
                    # 解析频道行，格式为: 频道名称,URL$城市
                    parts = line.split(",", 1)
                    if len(parts) == 2:
                        channel_name = parts[0].strip()
                        channel_part = parts[1].strip()
                        
                        # 检查是否有城市标记
                        if "$" in channel_part:
                            channel_url, city = channel_part.rsplit("$", 1)
                        else:
                            channel_url = channel_part
                            city = city_name
                        
                        # 将频道添加到对应分类和频道名称下
                        if channel_name not in all_channels_by_category[current_category]:
                            all_channels_by_category[current_category][channel_name] = []
                        
                        all_channels_by_category[current_category][channel_name].append((channel_url, city))
    
    # 按照指定顺序对分类进行排序
    sorted_categories = sort_categories_by_order(all_channels_by_category)
    
    # 写入合并的TXT文件
    with open("zubo_all.txt", "w", encoding="utf-8") as f:
        f.write(f"{current_time}更新,#genre#\n")
        f.write(f"浙江卫视,http://ali-m-l.cztv.com/channels/lantian/channel001/1080p.m3u8\n")
        
        # 按照排序后的分类写入
        for category in sorted_categories:
            f.write(f"{category},#genre#\n")
            
            # 获取该分类下所有频道名称，并按分类规则排序
            if category in all_channels_by_category:
                channel_names = list(all_channels_by_category[category].keys())
                sorted_channel_names = sort_channels_by_category(category, channel_names)
                
                for channel_name in sorted_channel_names:
                    # 写入该频道的所有源
                    for channel_url, city in all_channels_by_category[category][channel_name]:
                        f.write(f"{channel_name},{channel_url}${city}\n")
    
    total_sources = sum(len(sources) for category in all_channels_by_category.values() for sources in category.values())
    print(f"已合并TXT文件: zubo_all.txt (共{len(all_channels_by_category)}个分类，{total_sources}个源)")
    
    # 合并M3U文件
    with open("zubo_all.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        
        # 添加示例频道
        zjws_logo = logo_dict.get("浙江卫视", "")
        if zjws_logo:
            f.write(f'#EXTINF:-1 tvg-id="" tvg-name="浙江卫视" tvg-logo="{zjws_logo}" group-title="示例频道",浙江卫视\n')
        else:
            f.write(f'#EXTINF:-1 tvg-id="" tvg-name="浙江卫视" group-title="示例频道",浙江卫视\n')
        f.write(f"http://ali-m-l.cztv.com/channels/lantian/channel001/1080p.m3u8\n")
        
        # 按照排序后的分类写入
        for category in sorted_categories:
            if category in all_channels_by_category:
                # 获取该分类下所有频道名称，并按分类规则排序
                channel_names = list(all_channels_by_category[category].keys())
                sorted_channel_names = sort_channels_by_category(category, channel_names)
                
                for channel_name in sorted_channel_names:
                    # 查找台标
                    logo_url = logo_dict.get(channel_name, "")
                    
                    # 写入该频道的所有源
                    for channel_url, city in all_channels_by_category[category][channel_name]:
                        display_name = f"{channel_name}${city}"
                        
                        if logo_url:
                            f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" tvg-logo="{logo_url}" group-title="{category}",{display_name}\n')
                        else:
                            f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" group-title="{category}",{display_name}\n')
                        f.write(f"{channel_url}\n")
    
    print(f"已合并M3U文件: zubo_all.m3u")
    
    # 同时生成一个简化版的合并文件，每个频道只保留一个源
    with open("zubo_simple.txt", "w", encoding="utf-8") as f:
        f.write(f"{current_time}更新,#genre#\n")
        f.write(f"浙江卫视,http://ali-m-l.cztv.com/channels/lantian/channel001/1080p.m3u8\n")
        
        for category in sorted_categories:
            f.write(f"{category},#genre#\n")
            
            if category in all_channels_by_category:
                # 获取该分类下所有频道名称，并按分类规则排序
                channel_names = list(all_channels_by_category[category].keys())
                sorted_channel_names = sort_channels_by_category(category, channel_names)
                
                for channel_name in sorted_channel_names:
                    # 只取每个频道的第一个源
                    if all_channels_by_category[category][channel_name]:
                        channel_url, city = all_channels_by_category[category][channel_name][0]
                        f.write(f"{channel_name},{channel_url}\n")
    
    print(f"已生成简化版TXT文件: zubo_simple.txt")

def main():
    print("="*60)
    print("组播源处理系统")
    print("="*60)
    
    # 创建必要的目录
    os.makedirs('ip', exist_ok=True)
    os.makedirs('template', exist_ok=True)
    os.makedirs('output', exist_ok=True)
    
    # 检查必要的目录和文件
    for city in CITY_STREAMS:
        config_file = f"ip/{city}.txt"
        template_file = f"template/{city}.txt"
        
        if not os.path.exists(config_file):
            print(f"警告: 配置文件 {config_file} 不存在，正在创建示例文件")
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write("# 格式: IP:端口,option (option可选，默认0)\n")
                f.write("# 示例:\n")
                f.write("114.107.2.156:2000,0\n")
                f.write("114.107.2.156:2000,1\n")
        
        if not os.path.exists(template_file):
            print(f"警告: 频道模板文件 {template_file} 不存在，正在创建示例模板")
            os.makedirs('template', exist_ok=True)
            with open(template_file, 'w', encoding='utf-8') as f:
                f.write("# 频道模板文件格式\n")
                f.write("# 分类名称,#genre#\n")
                f.write("# 频道名称,http://ipipip/频道地址\n\n")
                f.write("央视频道,#genre#\n")
                f.write("CCTV1,http://ipipip/rtp/238.1.78.166:7200\n")
                f.write("CCTV2,http://ipipip/rtp/238.1.78.235:7752\n")
                f.write("卫视频道,#genre#\n")
                f.write(f"{city}卫视,http://ipipip/{CITY_STREAMS[city][0]}\n")
    
    # 处理每个城市的IP
    for city_name in CITY_STREAMS:
        print(f"\n{'='*60}")
        print(f"处理城市: {city_name}")
        print(f"{'='*60}")
        
        # 第一步：验证并更新IP文件
        valid_ips = validate_city_ips(city_name)
        
        if not valid_ips:
            print(f"{city_name} 没有可用的IP，跳过")
            continue
        
        # 第二步：获取前3名IP
        top_ips = get_top_ips_for_city(city_name, top_n=3)
        
        if not top_ips or len(top_ips) < 3:
            print(f"{city_name} 没有找到足够的可用IP（需要3个），跳过")
            continue
        
        # 第三步：读取台标文件
        logo_dict = read_logo_file()
        
        # 第四步：生成文件
        generate_files_for_city(city_name, top_ips, logo_dict)
        
        # 城市间延迟
        time.sleep(2)
    
    # 合并所有文件
    print(f"\n{'='*60}")
    print("开始合并所有文件...")
    print(f"{'='*60}")
    merge_all_files()
    
    print(f"\n{'='*60}")
    print("所有处理完成！")
    print(f"输出文件:")
    print(f"  - 单个城市文件: output/目录下")
    print(f"  - 合并文件: zubo_all.txt, zubo_all.m3u")
    print(f"  - 简化文件: zubo_simple.txt (每个频道只保留一个源)")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
