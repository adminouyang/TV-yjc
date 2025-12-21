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
import re
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 城市特定的测试流地址
CITY_STREAMS = {
    "安徽电信": ["rtp/238.1.79.27:4328"],
    "北京电信": ["rtp/225.1.8.21:8002"],
    "北京联通": ["rtp/239.3.1.241:8000"],
    "江苏电信": ["udp/239.49.8.19:9614"],
    "四川电信": ["udp/239.93.0.169:5140"],
    # 可以根据需要添加更多城市
}

# 远程GitHub仓库的基础URL
GITHUB_BASE_URL = "https://raw.githubusercontent.com/q1017673817/iptvz/refs/heads/main"

def get_city_config(city_name):
    """根据城市名获取配置"""
    if city_name in CITY_STREAMS:
        return {
            "ip_url": f"{GITHUB_BASE_URL}/ip/{city_name}_ip.txt",
            "template_url": f"{GITHUB_BASE_URL}/template/template_{city_name}.txt",
            "test_streams": CITY_STREAMS[city_name]
        }
    return None

def get_headers():
    """获取固定的请求头"""
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
        'Range': 'bytes=0-',
    }

def fetch_remote_content(url, max_retries=3):
    """从远程URL获取内容"""
    for attempt in range(max_retries):
        try:
            headers = get_headers()
            response = requests.get(url, headers=headers, timeout=10, verify=False)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                return None
    return None

def download_file_from_url(url, local_path):
    """从URL下载文件到本地"""
    try:
        content = fetch_remote_content(url)
        if content:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✓ 下载文件成功: {local_path}")
            return True
        else:
            print(f"× 下载文件失败: {url}")
            return False
    except Exception as e:
        print(f"× 下载文件异常: {url}, 错误: {e}")
        return False

def clean_ip_line(ip_line):
    """清理IP行，移除后面的速度值和多余空格"""
    if not ip_line:
        return ""
    
    # 移除注释
    if '#' in ip_line:
        ip_line = ip_line.split('#')[0]
    
    ip_line = ip_line.strip()
    
    # 如果行中包含"KB/s"，则移除速度值
    if 'KB/s' in ip_line:
        kb_s_index = ip_line.find('KB/s')
        if kb_s_index > 0:
            i = kb_s_index - 1
            while i >= 0 and (ip_line[i].isdigit() or ip_line[i] in ' .'):
                i -= 1
            ip_line = ip_line[:i+1].strip()
    
    # 如果行中包含多个空格，只保留IP:端口部分
    if ' ' in ip_line:
        parts = ip_line.split()
        if parts:
            ip_line = parts[0].strip()
    
    return ip_line

def read_channel_template():
    """读取本地频道模板文件"""
    template_file = "template/demo.txt"
    if not os.path.exists(template_file):
        print(f"频道模板文件不存在: {template_file}")
        return {}
    
    print(f"读取频道模板文件: {template_file}")
    
    channel_template = {}
    current_category = None
    current_channels = []
    
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                if ",#genre#" in line:
                    if current_category and current_channels:
                        channel_template[current_category] = current_channels.copy()
                    
                    current_category = line.replace(",#genre#", "").strip()
                    current_channels = []
                    print(f"  发现分类: {current_category}")
                elif "|" in line:
                    parts = [part.strip() for part in line.split("|") if part.strip()]
                    if len(parts) >= 1:
                        main_channel = parts[0]
                        aliases = parts[1:] if len(parts) > 1 else []
                        current_channels.append((main_channel, aliases))
        
        if current_category and current_channels:
            channel_template[current_category] = current_channels.copy()
        
        total_categories = len(channel_template)
        total_channels = sum(len(channels) for channels in channel_template.values())
        print(f"  共读取到 {total_categories} 个分类，总计 {total_channels} 个频道")
        
        return channel_template
    except Exception as e:
        print(f"读取频道模板文件错误: {e}")
        return {}

def clean_channel_name(channel_name):
    """清理频道名称，移除特殊符号和空格"""
    if not channel_name:
        return ""
    
    cleaned_name = channel_name.strip()
    cleaned_name = re.sub(r'\s+', '', cleaned_name)
    cleaned_name = re.sub(r'[【】\[\]()（）]', '', cleaned_name)
    
    return cleaned_name

def is_channel_match(actual_channel, template_channel):
    """检查实际频道是否匹配模板频道"""
    if not actual_channel or not template_channel:
        return False
    
    cleaned_actual = clean_channel_name(actual_channel)
    cleaned_template = clean_channel_name(template_channel)
    
    if not cleaned_actual or not cleaned_template:
        return False
    
    if cleaned_template.startswith("CCTV"):
        if cleaned_actual == cleaned_template:
            return True
        
        if cleaned_actual.startswith(cleaned_template):
            next_char = cleaned_actual[len(cleaned_template):]
            if not next_char or not next_char[0].isdigit():
                return True
        
        return False
    else:
        return cleaned_template in cleaned_actual

def get_channel_category(channel_name, channel_template):
    """根据频道名称获取对应的分类"""
    if not channel_name:
        return "其它频道"
    
    for category, channels in channel_template.items():
        for main_channel, aliases in channels:
            if is_channel_match(channel_name, main_channel):
                return category
            
            for alias in aliases:
                if is_channel_match(channel_name, alias):
                    return category
    
    return "其它频道"

def get_main_channel_name(channel_name, channel_template):
    """根据频道名称获取对应的主频道名"""
    if not channel_name:
        return channel_name
    
    for category, channels in channel_template.items():
        for main_channel, aliases in channels:
            if is_channel_match(channel_name, main_channel):
                return main_channel
            
            for alias in aliases:
                if is_channel_match(channel_name, alias):
                    return main_channel
    
    return channel_name

def test_stream_speed(stream_url, timeout=5):
    """测试流媒体速度，返回速度(KB/s)和是否成功"""
    try:
        headers = get_headers()
        start_time = time.time()
        
        response = requests.get(stream_url, headers=headers, timeout=timeout, 
                              verify=False, allow_redirects=True, stream=True)
        
        if response.status_code not in [200, 206]:
            return 0, False
        
        downloaded = 0
        chunk_size = 10 * 1024
        max_download = 100 * 1024
        
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

def test_ip_single(ip_port, test_stream, timeout=5):
    """测试单个IP，返回速度"""
    stream_url = f"http://{ip_port}/{test_stream}"
    
    try:
        time.sleep(random.uniform(0.1, 0.3))
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

def validate_city_ips(city_name, city_config):
    """验证城市IP文件中的IP，删除不可用的，保留可用的"""
    ip_url = city_config["ip_url"]
    test_stream = city_config["test_streams"][0] if city_config["test_streams"] else None
    
    if not test_stream:
        print(f"{city_name} 没有测试流地址，跳过IP验证")
        return []
    
    # 从远程获取IP列表
    print(f"正在下载IP列表: {ip_url}")
    ip_content = fetch_remote_content(ip_url)
    if not ip_content:
        print(f"获取IP列表失败: {ip_url}")
        return []
    
    # 解析IP列表
    ip_configs = []
    for line in ip_content.split('\n'):
        line = line.strip()
        if line and ":" in line and not line.startswith('#'):
            cleaned_ip = clean_ip_line(line)
            if cleaned_ip and ":" in cleaned_ip:
                ip_configs.append(cleaned_ip)
    
    if not ip_configs:
        print(f"{city_name} 没有可用的IP")
        return []
    
    print(f"从远程获取到 {len(ip_configs)} 个IP")
    print(f"\n开始验证 {city_name} 的 {len(ip_configs)} 个IP...")
    valid_ips = []
    
    # 使用线程池并发测试
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for ip_port in ip_configs:
            future = executor.submit(test_ip_single, ip_port, test_stream)
            futures.append(future)
        
        for future in as_completed(futures):
            ip_port, speed = future.result()
            if ip_port:
                valid_ips.append((ip_port, speed))
    
    # 按速度排序
    valid_ips.sort(key=lambda x: x[1], reverse=True)
    
    # 保存到本地IP文件
    local_ip_file = f"ip/{city_name}_ip.txt"
    os.makedirs('ip', exist_ok=True)
    with open(local_ip_file, 'w', encoding='utf-8') as f:
        for ip_port, speed in valid_ips:
            f.write(f"{ip_port} {speed:.2f} KB/s\n")
    
    print(f"\n{city_name} 验证完成:")
    print(f"  - 总共测试: {len(ip_configs)} 个IP")
    print(f"  - 可用IP: {len(valid_ips)} 个")
    print(f"  - 已保存到: {local_ip_file}")
    
    return valid_ips

def get_top_ips_for_city(city_name, city_config, top_n=3):
    """获取城市IP列表中的前N名IP"""
    # 从本地文件读取（由validate_city_ips生成）
    local_ip_file = f"ip/{city_name}_ip.txt"
    if not os.path.exists(local_ip_file):
        print(f"本地IP文件不存在: {local_ip_file}，跳过")
        return []
    
    # 读取IP列表
    ip_configs = []
    with open(local_ip_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and ":" in line and not line.startswith('#'):
                cleaned_ip = clean_ip_line(line)
                if cleaned_ip and ":" in cleaned_ip:
                    ip_configs.append(cleaned_ip)
    
    if not ip_configs:
        print(f"{city_name} 没有可用的IP")
        return []
    
    test_stream = city_config["test_streams"][0] if city_config["test_streams"] else None
    if not test_stream:
        print(f"{city_name} 没有测试流地址")
        return []
    
    print(f"\n开始测试 {city_name} 的 {len(ip_configs)} 个IP...")
    
    all_valid_ips = []
    
    # 首先测试已有的IP
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(test_ip_single, ip, test_stream): ip for ip in ip_configs}
        
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

def download_template_file(city_name, city_config):
    """下载城市对应的频道模板文件"""
    template_url = city_config["template_url"]
    local_template_file = f"template/{city_name}.txt"
    
    # 先检查本地是否有模板文件
    if os.path.exists(local_template_file):
        print(f"使用本地模板文件: {local_template_file}")
        return read_template_file(city_name)
    
    # 尝试从远程下载模板文件
    print(f"正在下载频道模板: {template_url}")
    success = download_file_from_url(template_url, local_template_file)
    if not success:
        print(f"下载频道模板失败: {template_url}")
        return None
    
    return read_template_file(city_name)

def read_template_file(city_name):
    """读取城市对应的频道模板文件（从本地）"""
    template_file = f"template/{city_name}.txt"
    if not os.path.exists(template_file):
        print(f"频道模板文件不存在: {template_file}")
        return None
    
    print(f"读取频道模板: {template_file}")
    
    categories = []
    current_category = ""
    current_channels = []
    
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                if ",#genre#" in line:
                    if current_category and current_channels:
                        categories.append((current_category, current_channels))
                    
                    current_category = line.replace(",#genre#", "").strip()
                    current_channels = []
                elif line and "," in line:
                    parts = line.split(",", 1)
                    if len(parts) == 2:
                        channel_name = parts[0].strip()
                        channel_url = parts[1].strip()
                        current_channels.append((channel_name, channel_url))
        
        if current_category and current_channels:
            categories.append((current_category, current_channels))
        
        print(f"  共读取到 {len(categories)} 个分类，总计 {sum(len(channels) for _, channels in categories)} 个频道")
        return categories
    except Exception as e:
        print(f"读取模板文件错误: {e}")
        return None

def read_logo_file():
    """读取本地台标文件"""
    logo_dict = {}
    local_logo_file = "template/logo.txt"
    
    if os.path.exists(local_logo_file):
        try:
            with open(local_logo_file, 'r', encoding='utf-8') as f:
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
        print(f"台标文件不存在: {local_logo_file}")
    
    return logo_dict

def generate_files_for_city(city_name, top_ips, logo_dict, categories):
    """为城市生成TXT和M3U文件，使用可用的IP生成源（有几个用几个）"""
    if not categories:
        print(f"{city_name} 没有频道模板，跳过文件生成")
        return False
    
    if not top_ips:
        print(f"{city_name} 没有可用的IP，跳过文件生成")
        return False
    
    # 创建输出目录
    os.makedirs('output', exist_ok=True)
    
    # 使用所有可用的IP
    available_ips = [ip for ip, _ in top_ips]
    
    # 生成TXT文件
    txt_file = f"output/{city_name}.txt"
    m3u_file = f"output/{city_name}.m3u"
    
    try:
        with open(txt_file, 'w', encoding='utf-8') as txt_f, \
             open(m3u_file, 'w', encoding='utf-8') as m3u_f:
            
            m3u_f.write("#EXTM3U\n")
            
            channel_count = 0
            
            for category, channels in categories:
                # 写入分类标题
                txt_f.write(f"{category},#genre#\n")
                
                for channel_name, channel_url in channels:
                    # 为每个频道生成源，使用所有可用的IP
                    for i, ip_port in enumerate(available_ips, 1):
                        # 替换ipipip为实际IP:端口
                        new_url = channel_url.replace("ipipip", ip_port)
                        
                        # 写入TXT文件
                        txt_f.write(f"{channel_name},{new_url}${city_name}\n")
                        
                        # 写入M3U文件
                        logo_url = logo_dict.get(channel_name, "")
                        
                        if logo_url:
                            m3u_f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" tvg-logo="{logo_url}" group-title="{category}",{channel_name}${city_name}\n')
                        else:
                            m3u_f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" group-title="{category}",{channel_name}${city_name}\n')
                        m3u_f.write(f"{new_url}\n")
                        
                        channel_count += 1
        
        print(f"✓ TXT文件: {txt_file} (共{channel_count}个频道，每个频道{len(available_ips)}个源)")
        print(f"✓ M3U文件: {m3u_file}")
        return True
    except Exception as e:
        print(f"× 生成文件失败: {e}")
        return False

def merge_all_files():
    """合并所有城市的TXT和M3U文件，按照频道模板排序"""
    try:
        txt_files = glob.glob("output/*.txt")
        m3u_files = glob.glob("output/*.m3u")
        
        if not txt_files or not m3u_files:
            print("没有找到输出文件可合并")
            return
        
        # 按城市名称排序
        txt_files.sort()
        m3u_files.sort()
        
        # 读取频道模板
        channel_template = read_channel_template()
        if not channel_template:
            print("没有读取到频道模板，使用默认排序")
            return
        
        # 读取台标文件
        logo_dict = read_logo_file()
        
        # 生成时间
        try:
            now = datetime.datetime.now(timezone.utc) + timedelta(hours=8)
        except:
            now = datetime.datetime.utcnow() + timedelta(hours=8)
        current_time = now.strftime("%Y/%m/%d %H:%M")
        
        # 收集所有频道
        all_channels = {}
        
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
                    elif line and "," in line and current_category:
                        parts = line.split(",", 1)
                        if len(parts) == 2:
                            channel_name = parts[0].strip()
                            channel_part = parts[1].strip()
                            
                            if "$" in channel_part:
                                channel_url, city = channel_part.rsplit("$", 1)
                            else:
                                channel_url = channel_part
                                city = city_name
                            
                            if channel_name not in all_channels:
                                all_channels[channel_name] = {}
                            
                            if current_category not in all_channels[channel_name]:
                                all_channels[channel_name][current_category] = []
                            
                            all_channels[channel_name][current_category].append((channel_url, city))
        
        # 重新组织频道，按照模板分类
        organized_channels = {}
        
        # 初始化所有分类
        for category in channel_template.keys():
            organized_channels[category] = {}
        
        # 添加"其它频道"分类
        organized_channels["其它频道"] = {}
        
        # 将频道分配到模板分类中
        for channel_name, categories_dict in all_channels.items():
            category = get_channel_category(channel_name, channel_template)
            main_channel_name = get_main_channel_name(channel_name, channel_template)
            
            if category not in organized_channels:
                organized_channels[category] = {}
            
            if main_channel_name not in organized_channels[category]:
                organized_channels[category][main_channel_name] = []
            
            for original_category, sources in categories_dict.items():
                for url, city in sources:
                    organized_channels[category][main_channel_name].append((channel_name, url, city))
        
        # 写入合并的TXT文件
        with open("zubo_all.txt", "w", encoding="utf-8") as f:
            f.write(f"{current_time}更新,#genre#\n")
            f.write(f"浙江卫视,http://ali-m-l.cztv.com/channels/lantian/channel001/1080p.m3u8\n")
            
            for category in channel_template.keys():
                if category in organized_channels and organized_channels[category]:
                    f.write(f"{category},#genre#\n")
                    
                    for main_channel, aliases in channel_template[category]:
                        if main_channel in organized_channels[category]:
                            for channel_name, url, city in organized_channels[category][main_channel]:
                                f.write(f"{channel_name},{url}${city}\n")
        
        # 处理"其它频道"分类
        if organized_channels.get("其它频道") and organized_channels["其它频道"]:
            with open("zubo_all.txt", "a", encoding="utf-8") as f:
                f.write(f"其它频道,#genre#\n")
                
                other_channels = sorted(organized_channels["其它频道"].keys())
                for main_channel in other_channels:
                    for channel_name, url, city in organized_channels["其它频道"][main_channel]:
                        f.write(f"{channel_name},{url}${city}\n")
        
        # 计算总源数
        total_sources = 0
        for category in organized_channels.values():
            for main_channel in category.values():
                total_sources += len(main_channel)
        
        print(f"✓ 已合并TXT文件: zubo_all.txt (共{len(organized_channels)}个分类，{total_sources}个源)")
        
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
            
            for category in channel_template.keys():
                if category in organized_channels and organized_channels[category]:
                    for main_channel, aliases in channel_template[category]:
                        if main_channel in organized_channels[category]:
                            for channel_name, url, city in organized_channels[category][main_channel]:
                                logo_url = logo_dict.get(channel_name, "")
                                display_name = f"{channel_name}"
                                
                                if logo_url:
                                    f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" tvg-logo="{logo_url}" group-title="{category}",{display_name}\n')
                                else:
                                    f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" group-title="{category}",{display_name}\n')
                                f.write(f"{url}\n")
            
            if organized_channels.get("其它频道") and organized_channels["其它频道"]:
                other_channels = sorted(organized_channels["其它频道"].keys())
                for main_channel in other_channels:
                    for channel_name, url, city in organized_channels["其它频道"][main_channel]:
                        logo_url = logo_dict.get(channel_name, "")
                        display_name = f"{channel_name}"
                        
                        if logo_url:
                            f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" tvg-logo="{logo_url}" group-title="其它频道",{display_name}\n')
                        else:
                            f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" group-title="其它频道",{display_name}\n')
                        f.write(f"{url}\n")
        
        print(f"✓ 已合并M3U文件: zubo_all.m3u")
        
        # 生成简化版
        with open("zubo_simple.txt", "w", encoding="utf-8") as f:
            f.write(f"{current_time}更新,#genre#\n")
            f.write(f"浙江卫视,http://ali-m-l.cztv.com/channels/lantian/channel001/1080p.m3u8\n")
            
            for category in channel_template.keys():
                if category in organized_channels and organized_channels[category]:
                    f.write(f"{category},#genre#\n")
                    
                    written_channels = set()
                    for main_channel, aliases in channel_template[category]:
                        if main_channel in organized_channels[category] and organized_channels[category][main_channel]:
                            for channel_name, url, city in organized_channels[category][main_channel]:
                                if channel_name not in written_channels:
                                    f.write(f"{channel_name},{url}\n")
                                    written_channels.add(channel_name)
                                    break
            
            if organized_channels.get("其它频道") and organized_channels["其它频道"]:
                f.write(f"其它频道,#genre#\n")
                written_channels = set()
                other_channels = sorted(organized_channels["其它频道"].keys())
                for main_channel in other_channels:
                    if organized_channels["其它频道"][main_channel]:
                        for channel_name, url, city in organized_channels["其它频道"][main_channel]:
                            if channel_name not in written_channels:
                                f.write(f"{channel_name},{url}\n")
                                written_channels.add(channel_name)
                                break
        
        print(f"✓ 已生成简化版TXT文件: zubo_simple.txt")
    
    except Exception as e:
        print(f"× 合并文件时发生错误: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("="*60)
    print("组播源处理系统")
    print(f"GitHub仓库: {GITHUB_BASE_URL}")
    print("="*60)
    
    # 创建必要的目录
    os.makedirs('ip', exist_ok=True)
    os.makedirs('template', exist_ok=True)
    os.makedirs('output', exist_ok=True)
    
    # 检查必要的本地文件
    if not os.path.exists("template/demo.txt"):
        print("× 请确保 template/demo.txt 文件存在")
        return
    
    if not os.path.exists("template/logo.txt"):
        print("× 请确保 template/logo.txt 文件存在")
        return
    
    # 处理每个城市
    processed_cities = []
    
    for city_name in CITY_STREAMS:
        print(f"\n{'='*60}")
        print(f"处理城市: {city_name}")
        print(f"{'='*60}")
        
        # 获取城市配置
        city_config = get_city_config(city_name)
        if not city_config:
            print(f"× 无法获取城市配置: {city_name}，跳过")
            continue
        
        # 第一步：验证并更新IP文件
        valid_ips = validate_city_ips(city_name, city_config)
        
        if not valid_ips:
            print(f"× {city_name} 没有可用的IP，跳过")
            continue
        
        # 第二步：获取可用的IP（最多3个，但实际有多少用多少）
        top_ips = valid_ips[:3]  # 取前3个，但实际可能不足3个
        
        print(f"✓ {city_name} 共有 {len(valid_ips)} 个可用IP，将使用前 {len(top_ips)} 个")
        
        # 第三步：下载并读取频道模板
        categories = download_template_file(city_name, city_config)
        
        if not categories:
            print(f"× {city_name} 没有频道模板，跳过")
            continue
        
        # 第四步：读取台标文件
        logo_dict = read_logo_file()
        
        # 第五步：生成文件（有多少IP就用多少）
        success = generate_files_for_city(city_name, top_ips, logo_dict, categories)
        
        if success:
            processed_cities.append(city_name)
        
        # 城市间延迟
        time.sleep(2)
    
    # 合并所有文件
    if processed_cities:
        print(f"\n{'='*60}")
        print("开始合并所有文件...")
        print(f"已处理城市: {', '.join(processed_cities)}")
        print(f"{'='*60}")
        merge_all_files()
    else:
        print(f"\n{'='*60}")
        print("没有成功处理任何城市，无法合并文件")
        print(f"{'='*60}")
    
    print(f"\n{'='*60}")
    print("处理完成！")
    print(f"请检查以下目录和文件:")
    print(f"  - IP文件: ip/目录")
    print(f"  - 模板文件: template/目录")
    print(f"  - 单个城市文件: output/目录")
    print(f"  - 合并文件: 当前目录下的 zubo_all.txt, zubo_all.m3u, zubo_simple.txt")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
