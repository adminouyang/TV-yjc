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
    "上海电信": ["rtp/239.45.3.146:5140"],
    # 可以根据需要添加更多城市
}

# 远程GitHub仓库的基础URL
GITHUB_BASE_URL = "https://raw.githubusercontent.com/q1017673817/iptvz/refs/heads/main"

# 设置工作目录
WORKING_DIR = os.getcwd()  # GitHub Actions的工作目录
MY_TV_DIR = os.path.join(WORKING_DIR, "my_tv")
OUTPUT_DIR = os.path.join(MY_TV_DIR, "output")

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
            print(f"  尝试获取内容: {url} (尝试 {attempt+1}/{max_retries})")
            response = requests.get(url, headers=headers, timeout=10, verify=False)
            response.raise_for_status()
            print(f"  获取内容成功: {url}, 长度: {len(response.text)} 字符")
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"  获取内容失败: {url}, 错误: {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                print(f"✗ 获取远程内容失败: {url}")
                return None
    return None

def download_file_from_url(url, local_path):
    """从URL下载文件到本地"""
    try:
        print(f"下载文件: {url} -> {local_path}")
        content = fetch_remote_content(url)
        if content:
            # 确保目录存在
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✓ 下载文件成功: {local_path}, 大小: {len(content)} 字符")
            return True
        else:
            print(f"✗ 下载文件失败: {url} (内容为空)")
            return False
    except Exception as e:
        print(f"✗ 下载文件异常: {url}, 错误: {e}")
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
    """读取频道模板文件（从本地缓存）"""
    template_file = os.path.join(MY_TV_DIR, "template", "demo.txt")
    if not os.path.exists(template_file):
        print(f"✗ 频道模板文件不存在: {template_file}")
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
        print(f"✓ 共读取到 {total_categories} 个分类，总计 {total_channels} 个频道")
        
        return channel_template
    except Exception as e:
        print(f"✗ 读取频道模板文件错误: {e}")
        return {}

def clean_channel_name(channel_name):
    """清理频道名称，移除特殊符号和空格，统一格式"""
    if not channel_name:
        return ""
    
    cleaned_name = channel_name.strip()
    
    # 移除常见的分隔符和特殊符号
    cleaned_name = re.sub(r'[【】\[\]()（）\-—－\s]', '', cleaned_name)
    
    # 将CCTV-X格式统一为CCTVX格式
    cleaned_name = re.sub(r'CCTV-(\d+)', r'CCTV\1', cleaned_name, flags=re.IGNORECASE)
    
    return cleaned_name.lower()  # 转换为小写以便比较

def is_channel_match(actual_channel, template_channel):
    """检查实际频道是否匹配模板频道（支持别名）"""
    if not actual_channel or not template_channel:
        return False
    
    cleaned_actual = clean_channel_name(actual_channel)
    cleaned_template = clean_channel_name(template_channel)
    
    if not cleaned_actual or not cleaned_template:
        return False
    
    # 如果完全相等，直接匹配
    if cleaned_actual == cleaned_template:
        return True
    
    # CCTV频道特殊处理
    if cleaned_template.startswith("cctv"):
        # 提取CCTV后面的数字
        actual_match = re.search(r'cctv(\d+)', cleaned_actual)
        template_match = re.search(r'cctv(\d+)', cleaned_template)
        
        if actual_match and template_match:
            # 如果都有数字，比较数字是否相同
            return actual_match.group(1) == template_match.group(1)
        elif actual_match or template_match:
            # 如果一个有数字一个没有，不匹配
            return False
        else:
            # 都没有数字，直接比较字符串
            return cleaned_actual == cleaned_template
    
    # 非CCTV频道，使用包含匹配
    return cleaned_template in cleaned_actual

def get_channel_category(channel_name, channel_template):
    """根据频道名称获取对应的分类"""
    if not channel_name:
        return "其它频道"
    
    cleaned_channel = clean_channel_name(channel_name)
    
    for category, channels in channel_template.items():
        for main_channel, aliases in channels:
            # 检查是否匹配主频道
            if is_channel_match(channel_name, main_channel):
                return category
            
            # 检查是否匹配别名
            for alias in aliases:
                if is_channel_match(channel_name, alias):
                    return category
    
    return "其它频道"

def get_main_channel_name(channel_name, channel_template):
    """根据频道名称获取对应的主频道名"""
    if not channel_name:
        return channel_name
    
    cleaned_channel = clean_channel_name(channel_name)
    
    for category, channels in channel_template.items():
        for main_channel, aliases in channels:
            # 检查是否匹配主频道
            if is_channel_match(channel_name, main_channel):
                return main_channel
            
            # 检查是否匹配别名
            for alias in aliases:
                if is_channel_match(channel_name, alias):
                    return main_channel
    
    return channel_name

def test_stream_speed(stream_url, timeout=8):
    """测试流媒体速度，返回速度(KB/s)和是否成功"""
    try:
        headers = get_headers()
        start_time = time.time()
        
        response = requests.get(stream_url, headers=headers, timeout=timeout, 
                              verify=False, allow_redirects=True, stream=True)
        
        if response.status_code not in [200, 206]:
            return 0, False
        
        downloaded = 0
        chunk_size = 100 * 1024
        max_download = 1000 * 1024
        
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

def test_ip_single(ip_port, test_stream, timeout=8):
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
    with ThreadPoolExecutor(max_workers=5) as executor:  # 减少线程数
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
    
    # 只取前3个，少于3个的全部取
    top_ips = valid_ips[:3]
    
    # 保存到my_tv/ip目录
    local_ip_file = os.path.join(MY_TV_DIR, "ip", f"{city_name}_ip.txt")
    os.makedirs(os.path.dirname(local_ip_file), exist_ok=True)
    
    if top_ips:
        with open(local_ip_file, 'w', encoding='utf-8') as f:
            for ip_port, speed in top_ips:
                f.write(f"{ip_port} {speed:.2f} KB/s\n")
        
        print(f"\n{city_name} 验证完成:")
        print(f"  - 总共测试: {len(ip_configs)} 个IP")
        print(f"  - 可用IP: {len(top_ips)} 个")
        print(f"  - 已保存到: {local_ip_file}")
        
        return top_ips
    else:
        # 如果没有可用IP，创建一个空文件
        with open(local_ip_file, 'w', encoding='utf-8') as f:
            pass
        print(f"\n{city_name} 验证完成: 没有可用的IP")
        return []

def get_top_ips_for_city(city_name, city_config):
    """获取城市IP列表中的IP - 直接从文件读取"""
    # 从my_tv/ip目录读取（由validate_city_ips生成）
    local_ip_file = os.path.join(MY_TV_DIR, "ip", f"{city_name}_ip.txt")
    if not os.path.exists(local_ip_file):
        print(f"本地IP文件不存在: {local_ip_file}，跳过")
        return []
    
    # 检查文件大小
    file_size = os.path.getsize(local_ip_file)
    if file_size == 0:
        print(f"{city_name} IP文件为空，没有可用的IP")
        return []
    
    # 读取IP列表和速度
    ip_speeds = []
    with open(local_ip_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and "KB/s" in line:
                # 解析IP和速度
                parts = line.split()
                if len(parts) >= 2:
                    ip_port = parts[0]
                    # 提取速度值
                    for part in parts[1:]:
                        if 'KB/s' in part:
                            speed_str = part.replace('KB/s', '')
                            try:
                                speed = float(speed_str)
                                ip_speeds.append((ip_port, speed))
                                break
                            except ValueError:
                                pass
                    else:
                        # 如果没有找到包含KB/s的部分，但有两个部分，尝试解析
                        if len(parts) >= 2:
                            try:
                                speed = float(parts[1])
                                ip_speeds.append((parts[0], speed))
                            except ValueError:
                                pass
    if not ip_speeds:
        print(f"{city_name} 没有可用的IP（无法解析IP文件）")
        return []
    
    # 按速度排序
    ip_speeds.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\n{city_name} 读取到 {len(ip_speeds)} 个可用IP:")
    for i, (ip, speed) in enumerate(ip_speeds, 1):
        print(f"  第{i}名: {ip} - 速度: {speed:.2f} KB/s")
    
    return ip_speeds

def download_template_file(city_name, city_config):
    """下载城市对应的频道模板文件"""
    template_url = city_config["template_url"]
    local_template_file = os.path.join(MY_TV_DIR, "template", f"{city_name}.txt")
    
    # 先检查本地是否有模板文件
    if os.path.exists(local_template_file):
        print(f"使用本地模板文件: {local_template_file}")
        return read_template_file(city_name)
    
    # 尝试从远程下载模板文件
    print(f"正在下载频道模板: {template_url}")
    success = download_file_from_url(template_url, local_template_file)
    if not success:
        print(f"✗ 无法获取频道模板: {template_url}")
        print(f"请确保模板文件存在，或手动创建: {local_template_file}")
        return None
    
    return read_template_file(city_name)

def read_template_file(city_name):
    """读取城市对应的频道模板文件（从本地）- 去重版本"""
    template_file = os.path.join(MY_TV_DIR, "template", f"{city_name}.txt")
    if not os.path.exists(template_file):
        print(f"✗ 频道模板文件不存在: {template_file}")
        return None
    
    print(f"读取频道模板: {template_file}")
    
    channels = []  # 返回格式: [(channel_name, channel_url), ...]
    seen_channels = set()  # 用于去重
    
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                # 跳过分类行（包含,#genre#的行）
                if ",#genre#" in line:
                    continue
                
                # 处理频道行（格式：频道名称,URL）
                if "," in line:
                    parts = line.split(",", 1)
                    if len(parts) == 2:
                        channel_name = parts[0].strip()
                        channel_url = parts[1].strip()
                        
                        # 检查是否已经处理过这个频道
                        if channel_name not in seen_channels:
                            seen_channels.add(channel_name)
                            channels.append((channel_name, channel_url))
                        else:
                            print(f"  跳过重复频道: {channel_name} (第{line_num}行)")
        
        print(f"✓ 共读取到 {len(channels)} 个频道 (已去重)")
        if len(seen_channels) < len(channels):
            print(f"  原始文件有 {len(seen_channels)} 个唯一频道，去除了 {len(channels) - len(seen_channels)} 个重复项")
        return channels
    except Exception as e:
        print(f"✗ 读取模板文件错误: {e}")
        import traceback
        traceback.print_exc()
        return None

def read_logo_file():
    """读取本地台标文件"""
    logo_dict = {}
    local_logo_file = os.path.join(MY_TV_DIR, "template", "logo.txt")
    
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
            print(f"✓ 读取到 {len(logo_dict)} 个台标")
        except Exception as e:
            print(f"✗ 读取台标文件错误: {e}")
    else:
        print(f"✗ 台标文件不存在: {local_logo_file}")
    
    return logo_dict

def categorize_channels(channels, channel_template):
    """将频道按照demo.txt的分类进行分类"""
    categorized = {}
    
    for channel_name, channel_url in channels:
        # 获取频道分类
        category = get_channel_category(channel_name, channel_template)
        
        if category not in categorized:
            categorized[category] = []
        
        categorized[category].append((channel_name, channel_url))
    
    return categorized

def generate_files_for_city(city_name, top_ips, logo_dict, channels, channel_template):
    """为城市生成TXT和M3U文件，使用可用的IP生成源"""
    print(f"\n开始为 {city_name} 生成文件...")
    print(f"可用IP数量: {len(top_ips) if top_ips else 0}")
    print(f"频道数量: {len(channels) if channels else 0}")
    
    if not channels:
        print(f"✗ {city_name} 没有频道，跳过文件生成")
        return
    
    if not top_ips:
        print(f"✗ {city_name} 没有可用的IP，跳过文件生成")
        return
    
    # 清理output目录中可能的旧测试文件
    test_file = os.path.join(OUTPUT_DIR, "1.txt")
    if os.path.exists(test_file):
        try:
            os.remove(test_file)
            print(f"已删除测试文件: {test_file}")
        except:
            pass
    
    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 使用所有可用的IP
    available_ips = [ip for ip, _ in top_ips]
    print(f"将使用以下IP生成源: {available_ips}")
    
    # 对频道进行分类
    categorized_channels = categorize_channels(channels, channel_template)
    
    # 生成TXT文件
    txt_file = os.path.join(OUTPUT_DIR, f"{city_name}.txt")
    m3u_file = os.path.join(OUTPUT_DIR, f"{city_name}.m3u")
    
    try:
        txt_channel_count = 0
        m3u_channel_count = 0
        
        with open(txt_file, 'w', encoding='utf-8') as txt_f:
            for category, channel_list in categorized_channels.items():
                # 写入分类标题
                txt_f.write(f"{category},#genre#\n")
                
                for channel_name, channel_url in channel_list:
                    # 为每个频道生成源，使用所有可用的IP
                    for i, ip_port in enumerate(available_ips, 1):
                        # 替换ipipip为实际IP:端口
                        new_url = channel_url.replace("ipipip", ip_port)
                        
                        # 写入TXT文件
                        txt_f.write(f"{channel_name},{new_url}${city_name}\n")
                        txt_channel_count += 1
        
        print(f"✓ TXT文件生成成功: {txt_file} (共{txt_channel_count}个源)")
        
        with open(m3u_file, 'w', encoding='utf-8') as m3u_f:
            m3u_f.write("#EXTM3U\n")
            
            for category, channel_list in categorized_channels.items():
                for channel_name, channel_url in channel_list:
                    # 为每个频道生成源，使用所有可用的IP
                    for i, ip_port in enumerate(available_ips, 1):
                        # 替换ipipip为实际IP:端口
                        new_url = channel_url.replace("ipipip", ip_port)
                        
                        # 写入M3U文件
                        logo_url = logo_dict.get(channel_name, "")
                        
                        if logo_url:
                            m3u_f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" tvg-logo="{logo_url}" group-title="{category}",{channel_name}${city_name}\n')
                        else:
                            m3u_f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" group-title="{category}",{channel_name}${city_name}\n')
                        m3u_f.write(f"{new_url}\n")
                        m3u_channel_count += 1
        
        print(f"✓ M3U文件生成成功: {m3u_file} (共{m3u_channel_count}个源)")
        
        return txt_file, m3u_file
    
    except Exception as e:
        print(f"✗ 生成文件时出错: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def get_ip_speed(ip_port, city_name):
    """从IP文件中获取IP的速度"""
    ip_file = os.path.join(MY_TV_DIR, "ip", f"{city_name}_ip.txt")
    if not os.path.exists(ip_file):
        return 0
    
    try:
        with open(ip_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if ip_port in line and "KB/s" in line:
                    # 解析速度
                    parts = line.split()
                    for part in parts[1:]:
                        if 'KB/s' in part:
                            speed_str = part.replace('KB/s', '')
                            try:
                                return float(speed_str)
                            except ValueError:
                                pass
    except:
        pass
    
    return 0

def merge_all_files(channel_template, max_sources_per_channel=10):
    """合并所有城市的TXT和M3U文件，按照频道模板排序，每个频道最多保留max_sources_per_channel个源"""
    print(f"\n开始合并所有文件...")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"每个频道最多保留 {max_sources_per_channel} 个最快的源")
    
    try:
        # 列出输出目录中的文件
        print(f"输出目录中的文件:")
        output_files = []
        if os.path.exists(OUTPUT_DIR):
            for file in os.listdir(OUTPUT_DIR):
                file_path = os.path.join(OUTPUT_DIR, file)
                if os.path.isfile(file_path) and file.endswith(('.txt', '.m3u')):
                    output_files.append(file_path)
                    print(f"  - {file} ({os.path.getsize(file_path)} bytes)")
        
        txt_files = [f for f in output_files if f.endswith('.txt')]
        m3u_files = [f for f in output_files if f.endswith('.m3u')]
        
        print(f"找到 {len(txt_files)} 个TXT文件")
        print(f"找到 {len(m3u_files)} 个M3U文件")
        
        if not txt_files or not m3u_files:
            print("✗ 没有找到输出文件可合并")
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
        
        # 收集所有频道及其源
        all_channels_with_sources = {}  # 格式: {main_channel: [(speed, original_channel_name, url, city, ip_port), ...]}
        
        # 先收集所有频道的源
        for txt_file in txt_files:
            city_name = os.path.basename(txt_file).replace('.txt', '')
            print(f"处理文件: {txt_file} (城市: {city_name})")
            
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
                            
                            # 从URL中提取IP:端口
                            url_parts = channel_url.split('/')
                            if len(url_parts) >= 3:
                                ip_port = url_parts[2]  # http://ip_port/...
                                
                                # 获取IP速度
                                speed = get_ip_speed(ip_port, city)
                                
                                # 将频道名称转换为主频道名
                                main_channel_name = get_main_channel_name(channel_name, channel_template)
                                
                                if main_channel_name not in all_channels_with_sources:
                                    all_channels_with_sources[main_channel_name] = []
                                
                                all_channels_with_sources[main_channel_name].append((speed, channel_name, channel_url, city, ip_port))
        
        print(f"总共收集到 {len(all_channels_with_sources)} 个不同的频道（已转换为主频道）")
        
        # 对每个频道的源按速度排序，并限制数量
        organized_channels = {}
        
        # 初始化所有分类
        for category in channel_template.keys():
            organized_channels[category] = {}
        
        # 添加"其它频道"分类
        organized_channels["其它频道"] = {}
        
        # 将频道分配到模板分类中，并对每个频道的源进行排序和限制
        for main_channel_name, sources in all_channels_with_sources.items():
            # 按速度排序（从高到低）
            sources.sort(key=lambda x: x[0], reverse=True)
            
            # 限制每个频道的源数量
            limited_sources = sources[:max_sources_per_channel]
            
            # 获取频道分类
            category = get_channel_category(main_channel_name, channel_template)
            
            if category not in organized_channels:
                organized_channels[category] = {}
            
            if main_channel_name not in organized_channels[category]:
                organized_channels[category][main_channel_name] = []
            
            for speed, original_channel_name, url, city, ip_port in limited_sources:
                organized_channels[category][main_channel_name].append((original_channel_name, url, city))
        
        # 写入合并的TXT文件 - 保存在my_tv文件夹下
        merged_txt_file = os.path.join(MY_TV_DIR, "zubo_all.txt")
        with open(merged_txt_file, "w", encoding="utf-8") as f:
            f.write(f"{current_time}更新,#genre#\n")
            f.write(f"浙江卫视,http://ali-m-l.cztv.com/channels/lantian/channel001/1080p.m3u8\n")
            
            for category in channel_template.keys():
                if category in organized_channels and organized_channels[category]:
                    f.write(f"{category},#genre#\n")
                    
                    for main_channel, aliases in channel_template[category]:
                        if main_channel in organized_channels[category]:
                            for original_channel_name, url, city in organized_channels[category][main_channel]:
                                # 使用主频道名
                                f.write(f"{main_channel},{url}${city}\n")
        
        # 处理"其它频道"分类
        if organized_channels.get("其它频道") and organized_channels["其它频道"]:
            with open(merged_txt_file, "a", encoding="utf-8") as f:
                f.write(f"其它频道,#genre#\n")
                
                other_channels = sorted(organized_channels["其它频道"].keys())
                for main_channel in other_channels:
                    for original_channel_name, url, city in organized_channels["其它频道"][main_channel]:
                        f.write(f"{main_channel},{url}${city}\n")
        
        # 计算总源数
        total_sources = 0
        for category in organized_channels.values():
            for main_channel in category.values():
                total_sources += len(main_channel)
        
        print(f"✓ 已合并TXT文件: {merged_txt_file} (共{len(organized_channels)}个分类，{total_sources}个源)")
        
        # 合并M3U文件 - 保存在my_tv文件夹下
        merged_m3u_file = os.path.join(MY_TV_DIR, "zubo_all.m3u")
        with open(merged_m3u_file, "w", encoding="utf-8") as f:
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
                            for original_channel_name, url, city in organized_channels[category][main_channel]:
                                logo_url = logo_dict.get(original_channel_name, "")
                                # 使用主频道名
                                display_name = f"{main_channel}"
                                
                                if logo_url:
                                    f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{main_channel}" tvg-logo="{logo_url}" group-title="{category}",{display_name}\n')
                                else:
                                    f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{main_channel}" group-title="{category}",{display_name}\n')
                                f.write(f"{url}\n")
            
            if organized_channels.get("其它频道") and organized_channels["其它频道"]:
                other_channels = sorted(organized_channels["其它频道"].keys())
                for main_channel in other_channels:
                    for original_channel_name, url, city in organized_channels["其它频道"][main_channel]:
                        logo_url = logo_dict.get(original_channel_name, "")
                        display_name = f"{main_channel}"
                        
                        if logo_url:
                            f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{main_channel}" tvg-logo="{logo_url}" group-title="其它频道",{display_name}\n')
                        else:
                            f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{main_channel}" group-title="其它频道",{display_name}\n')
                        f.write(f"{url}\n")
        
        print(f"✓ 已合并M3U文件: {merged_m3u_file}")
        
        # 生成简化版 - 保存在my_tv文件夹下
        simple_txt_file = os.path.join(MY_TV_DIR, "zubo_simple.txt")
        with open(simple_txt_file, "w", encoding="utf-8") as f:
            f.write(f"{current_time}更新,#genre#\n")
            f.write(f"浙江卫视,http://ali-m-l.cztv.com/channels/lantian/channel001/1080p.m3u8\n")
            
            for category in channel_template.keys():
                if category in organized_channels and organized_channels[category]:
                    f.write(f"{category},#genre#\n")
                    
                    written_channels = set()
                    for main_channel, aliases in channel_template[category]:
                        if main_channel in organized_channels[category] and organized_channels[category][main_channel]:
                            for original_channel_name, url, city in organized_channels[category][main_channel]:
                                if main_channel not in written_channels:
                                    f.write(f"{main_channel},{url}\n")
                                    written_channels.add(main_channel)
                                    break
            
            if organized_channels.get("其它频道") and organized_channels["其它频道"]:
                f.write(f"其它频道,#genre#\n")
                written_channels = set()
                other_channels = sorted(organized_channels["其它频道"].keys())
                for main_channel in other_channels:
                    if main_channel not in written_channels and organized_channels["其它频道"][main_channel]:
                        for original_channel_name, url, city in organized_channels["其它频道"][main_channel]:
                            f.write(f"{main_channel},{url}\n")
                            written_channels.add(main_channel)
                            break
        
        print(f"✓ 已生成简化版TXT文件: {simple_txt_file}")
    
    except Exception as e:
        print(f"✗ 合并文件时发生错误: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("="*60)
    print("组播源处理系统")
    print(f"GitHub仓库: {GITHUB_BASE_URL}")
    print(f"工作目录: {WORKING_DIR}")
    print(f"my_tv目录: {MY_TV_DIR}")
    print("="*60)
    
    # 清理旧的输出目录
    if os.path.exists(OUTPUT_DIR):
        for file in os.listdir(OUTPUT_DIR):
            try:
                os.remove(os.path.join(OUTPUT_DIR, file))
            except:
                pass
    
    # 创建必要的目录
    os.makedirs(os.path.join(MY_TV_DIR, "ip"), exist_ok=True)
    os.makedirs(os.path.join(MY_TV_DIR, "template"), exist_ok=True)
    os.makedirs(os.path.join(MY_TV_DIR, "output"), exist_ok=True)
    
    # 读取频道模板（demo.txt）
    print(f"\n步骤1: 读取频道模板...")
    channel_template = read_channel_template()
    if not channel_template:
        print("✗ 无法读取频道模板，程序退出")
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
            print(f"✗ 无法获取城市配置: {city_name}，跳过")
            continue
        
        # 第一步：验证并更新IP文件
        print(f"步骤1: 验证IP...")
        top_ips = validate_city_ips(city_name, city_config)
        
        if not top_ips:
            print(f"✗ {city_name} 没有可用的IP，跳过")
            continue
        
        print(f"✓ {city_name} 共有 {len(top_ips)} 个可用IP，将全部使用")
        for i, (ip, speed) in enumerate(top_ips, 1):
            print(f"  第{i}名: {ip} - 速度: {speed:.2f} KB/s")
        
        # 第二步：下载并读取频道模板
        print(f"步骤2: 下载并读取频道模板...")
        channels = download_template_file(city_name, city_config)
        
        if not channels:
            print(f"✗ {city_name} 没有频道，跳过")
            continue
        
        # 第三步：读取台标文件
        print(f"步骤3: 读取台标文件...")
        logo_dict = read_logo_file()
        
        # 第四步：生成文件
        print(f"步骤4: 生成输出文件...")
        generate_files_for_city(city_name, top_ips, logo_dict, channels, channel_template)
        
        processed_cities.append(city_name)
        
        # 城市间延迟
        time.sleep(2)
    
    print(f"\n{'='*60}")
    print(f"城市处理完成:")
    print(f"  成功处理的城市: {processed_cities}")
    print(f"  失败的城市: {[city for city in CITY_STREAMS if city not in processed_cities]}")
    print(f"{'='*60}")
    
    # 只有成功处理了至少一个城市才进行合并
    if processed_cities:
        # 合并所有文件
        print(f"\n{'='*60}")
        print("开始合并所有文件...")
        print(f"{'='*60}")
        # 每个频道最多10个源
        merge_all_files(channel_template, max_sources_per_channel=10)
    else:
        print(f"\n✗ 没有成功处理任何城市，跳过合并")
    
    print(f"\n{'='*60}")
    print("所有处理完成！")
    print(f"输出文件:")
    print(f"  - IP文件: {os.path.join(MY_TV_DIR, 'ip')} 目录下")
    print(f"  - 单个城市文件: {OUTPUT_DIR} 目录下")
    print(f"  - 合并文件: {os.path.join(MY_TV_DIR, 'zubo_all.txt')} (每个频道最多10个最快的源)")
    print(f"  - 合并文件: {os.path.join(MY_TV_DIR, 'zubo_all.m3u')} (每个频道最多10个最快的源)")
    print(f"  - 简化文件: {os.path.join(MY_TV_DIR, 'zubo_simple.txt')} (每个频道1个最快的源)")
    print(f"{'='*60}")
    
    # 打印生成的文件列表
    print("\n生成的文件列表:")
    file_count = 0
    for root, dirs, files in os.walk(MY_TV_DIR):
        for file in files:
            if file.endswith(('.txt', '.m3u')):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, WORKING_DIR)
                file_size = os.path.getsize(file_path)
                print(f"  - {rel_path} ({file_size:,} bytes)")
                file_count += 1
    
    print(f"\n总计生成 {file_count} 个文件")

if __name__ == "__main__":
    main()
