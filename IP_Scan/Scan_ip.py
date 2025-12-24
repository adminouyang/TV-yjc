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
    "北京市电信": ["rtp/225.1.8.21:8002"],
    "北京市联通": ["rtp/239.3.1.241:8000"],
    "江苏电信": ["udp/239.49.8.19:9614"],
    "四川电信": ["udp/239.93.0.169:5140"],
}

def get_headers():
    """获取固定的请求头"""
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Connection': 'keep-alive',
        'Range': 'bytes=0-',
    }

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
        # 找到"KB/s"的位置
        kb_s_index = ip_line.find('KB/s')
        if kb_s_index > 0:
            # 向前查找数字的起始位置
            i = kb_s_index - 1
            while i >= 0 and (ip_line[i].isdigit() or ip_line[i] in ' .'):
                i -= 1
            ip_line = ip_line[:i+1].strip()
    
    # 如果行中包含多个空格，只保留IP:端口部分
    if ' ' in ip_line:
        # 按空格分割，取第一部分
        parts = ip_line.split()
        if parts:
            ip_line = parts[0].strip()
    
    return ip_line

def read_channel_template():
    """读取频道模板文件"""
    template_file = "template/demo.txt"
    if not os.path.exists(template_file):
        print(f"频道模板文件不存在: {template_file}")
        return {}
    
    print(f"读取频道模板文件: {template_file}")
    
    channel_template = {}  # 格式: {分类: [(主频道名, [别名1, 别名2, ...]), ...]}
    current_category = None
    current_channels = []
    
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                
                if ",#genre#" in line:
                    # 如果是分类行，保存上一个分类
                    if current_category and current_channels:
                        channel_template[current_category] = current_channels.copy()
                    
                    current_category = line.replace(",#genre#", "").strip()
                    current_channels = []
                    print(f"  发现分类: {current_category}")
                elif "|" in line:
                    # 如果是频道行，用|分隔
                    parts = [part.strip() for part in line.split("|") if part.strip()]
                    if len(parts) >= 1:
                        main_channel = parts[0]
                        aliases = parts[1:] if len(parts) > 1 else []
                        current_channels.append((main_channel, aliases))
        
        # 保存最后一个分类
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
    
    # 移除空格和特殊字符
    cleaned_name = channel_name.strip()
    cleaned_name = re.sub(r'\s+', '', cleaned_name)  # 移除所有空白字符
    cleaned_name = re.sub(r'[【】\[\]()（）]', '', cleaned_name)  # 移除括号
    
    return cleaned_name

def is_channel_match(actual_channel, template_channel):
    """检查实际频道是否匹配模板频道"""
    if not actual_channel or not template_channel:
        return False
    
    cleaned_actual = clean_channel_name(actual_channel)
    cleaned_template = clean_channel_name(template_channel)
    
    if not cleaned_actual or not cleaned_template:
        return False
    
    # 如果模板频道是"CCTV1"这样的格式，需要精确匹配，避免"CCTV1"匹配到"CCTV10"
    if cleaned_template.startswith("CCTV"):
        # 对于CCTV频道，需要精确匹配或前缀匹配
        # 例如："CCTV1"应该匹配"CCTV1"或"CCTV1高清"，但不应该匹配"CCTV10"
        if cleaned_actual == cleaned_template:
            return True
        
        # 检查是否以模板频道开头，并且下一个字符不是数字
        if cleaned_actual.startswith(cleaned_template):
            # 获取模板后的下一个字符
            next_char = cleaned_actual[len(cleaned_template):]
            if not next_char or not next_char[0].isdigit():
                return True
        
        return False
    else:
        # 对于非CCTV频道，使用包含匹配
        return cleaned_template in cleaned_actual

def get_channel_category(channel_name, channel_template):
    """根据频道名称获取对应的分类"""
    if not channel_name:
        return "其它频道"
    
    # 遍历模板中的所有分类和频道
    for category, channels in channel_template.items():
        for main_channel, aliases in channels:
            # 检查主频道名
            if is_channel_match(channel_name, main_channel):
                return category
            
            # 检查别名
            for alias in aliases:
                if is_channel_match(channel_name, alias):
                    return category
    
    # 如果没有找到匹配的分类，返回"其它频道"
    return "其它频道"

def get_main_channel_name(channel_name, channel_template):
    """根据频道名称获取对应的主频道名"""
    if not channel_name:
        return channel_name
    
    # 遍历模板中的所有分类和频道
    for category, channels in channel_template.items():
        for main_channel, aliases in channels:
            # 检查主频道名
            if is_channel_match(channel_name, main_channel):
                return main_channel
            
            # 检查别名
            for alias in aliases:
                if is_channel_match(channel_name, alias):
                    return main_channel
    
    # 如果没有找到匹配，返回原频道名
    return channel_name

def get_ips_for_city(city_name):
    """从IP_Scan/result_ip/路径读取IP地址"""
    # 从CITY_STREAMS中获取对应的省份/城市名称映射
    # 注意：这里假设CITY_STREAMS中的键与IP_Scan/result_ip/下的文件名一致
    # 例如："安徽电信"对应"安徽电信.txt"
    ip_file = f"result_ip/{city_name}.txt"
    
    if not os.path.exists(ip_file):
        print(f"IP文件不存在: {ip_file}")
        return []
    
    ip_list = []
    try:
        with open(ip_file, 'r', encoding='utf-8') as f:
            for line in f:
                cleaned_ip = clean_ip_line(line.strip())
                if cleaned_ip and ":" in cleaned_ip:
                    ip_list.append(cleaned_ip)
        
        print(f"从 {ip_file} 读取到 {len(ip_list)} 个IP地址")
        return ip_list
    except Exception as e:
        print(f"读取IP文件错误: {e}")
        return []

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

def generate_files_for_city(city_name, ip_list, logo_dict):
    """为城市生成TXT和M3U文件，使用IP列表中的所有IP生成多个源"""
    if not ip_list or len(ip_list) < 1:
        print(f"{city_name} 没有可用的IP，跳过文件生成")
        return
    
    # 读取频道模板
    categories = read_template_file(city_name)
    if not categories:
        print(f"{city_name} 没有频道模板，跳过文件生成")
        return
    
    # 创建输出目录
    os.makedirs('output', exist_ok=True)
    
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
                # 为每个频道生成多个源，使用IP列表中的所有IP
                for i, ip_port in enumerate(ip_list, 1):
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
        
        print(f"  TXT文件: {txt_file} (共{channel_count}个频道，每个频道{len(ip_list)}个源)")
        print(f"  M3U文件: {m3u_file}")
    
    return txt_file, m3u_file

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
        # 结构: {channel_name: {category: [(url, city), ...]}}
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
                            
                            # 将频道添加到字典
                            if channel_name not in all_channels:
                                all_channels[channel_name] = {}
                            
                            if current_category not in all_channels[channel_name]:
                                all_channels[channel_name][current_category] = []
                            
                            all_channels[channel_name][current_category].append((channel_url, city))
        
        # 重新组织频道，按照模板分类
        # 结构: {category: {main_channel_name: [(original_channel_name, url, city), ...]}}
        organized_channels = {}
        
        # 初始化所有分类
        for category in channel_template.keys():
            organized_channels[category] = {}
        
        # 添加"其它频道"分类
        organized_channels["其它频道"] = {}
        
        # 将频道分配到模板分类中
        for channel_name, categories_dict in all_channels.items():
            # 根据频道名称获取分类
            category = get_channel_category(channel_name, channel_template)
            
            # 获取主频道名
            main_channel_name = get_main_channel_name(channel_name, channel_template)
            
            if category not in organized_channels:
                organized_channels[category] = {}
            
            if main_channel_name not in organized_channels[category]:
                organized_channels[category][main_channel_name] = []
            
            # 添加所有源
            for original_category, sources in categories_dict.items():
                for url, city in sources:
                    organized_channels[category][main_channel_name].append((channel_name, url, city))
        
        # 写入合并的TXT文件
        with open("zubo_all.txt", "w", encoding="utf-8") as f:
            f.write(f"{current_time}更新,#genre#\n")
            f.write(f"浙江卫视,http://ali-m-l.cztv.com/channels/lantian/channel001/1080p.m3u8\n")
            
            # 按照模板定义的分类顺序写入
            for category in channel_template.keys():
                if category in organized_channels and organized_channels[category]:
                    f.write(f"{category},#genre#\n")
                    
                    # 按照模板中的频道顺序写入
                    for main_channel, aliases in channel_template[category]:
                        if main_channel in organized_channels[category]:
                            # 写入该主频道下的所有频道
                            for channel_name, url, city in organized_channels[category][main_channel]:
                                f.write(f"{channel_name},{url}${city}\n")
        
        # 处理"其它频道"分类
        if organized_channels.get("其它频道") and organized_channels["其它频道"]:
            with open("zubo_all.txt", "a", encoding="utf-8") as f:
                f.write(f"其它频道,#genre#\n")
                
                # 获取所有其它频道并按字母顺序排序
                other_channels = sorted(organized_channels["其它频道"].keys())
                for main_channel in other_channels:
                    for channel_name, url, city in organized_channels["其它频道"][main_channel]:
                        f.write(f"{channel_name},{url}${city}\n")
        
        # 计算总源数
        total_sources = 0
        for category in organized_channels.values():
            for main_channel in category.values():
                total_sources += len(main_channel)
        
        print(f"已合并TXT文件: zubo_all.txt (共{len(organized_channels)}个分类，{total_sources}个源)")
        
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
            
            # 按照模板定义的分类顺序写入
            for category in channel_template.keys():
                if category in organized_channels and organized_channels[category]:
                    # 按照模板中的频道顺序写入
                    for main_channel, aliases in channel_template[category]:
                        if main_channel in organized_channels[category]:
                            # 写入该主频道下的所有频道
                            for channel_name, url, city in organized_channels[category][main_channel]:
                                # 查找台标
                                logo_url = logo_dict.get(channel_name, "")
                                
                                display_name = f"{channel_name}"   #${city}
                                
                                if logo_url:
                                    f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" tvg-logo="{logo_url}" group-title="{category}",{display_name}\n')
                                else:
                                    f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" group-title="{category}",{display_name}\n')
                                f.write(f"{url}\n")
            
            # 处理"其它频道"分类
            if organized_channels.get("其它频道") and organized_channels["其它频道"]:
                other_channels = sorted(organized_channels["其它频道"].keys())
                for main_channel in other_channels:
                    for channel_name, url, city in organized_channels["其它频道"][main_channel]:
                        # 查找台标
                        logo_url = logo_dict.get(channel_name, "")
                        
                        display_name = f"{channel_name}"  #${city}
                        
                        if logo_url:
                            f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" tvg-logo="{logo_url}" group-title="其它频道",{display_name}\n')
                        else:
                            f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" group-title="其它频道",{display_name}\n')
                        f.write(f"{url}\n")
        
        print(f"已合并M3U文件: zubo_all.m3u")
        
        # 同时生成一个简化版的合并文件，每个频道只保留一个源
        with open("zubo_simple.txt", "w", encoding="utf-8") as f:
            f.write(f"{current_time}更新,#genre#\n")
            f.write(f"浙江卫视,http://ali-m-l.cztv.com/channels/lantian/channel001/1080p.m3u8\n")
            
            # 按照模板定义的分类顺序写入
            for category in channel_template.keys():
                if category in organized_channels and organized_channels[category]:
                    f.write(f"{category},#genre#\n")
                    
                    # 按照模板中的频道顺序写入
                    written_channels = set()  # 记录已经写入的频道
                    for main_channel, aliases in channel_template[category]:
                        if main_channel in organized_channels[category] and organized_channels[category][main_channel]:
                            # 只取每个主频道的第一个源
                            for channel_name, url, city in organized_channels[category][main_channel]:
                                if channel_name not in written_channels:
                                    f.write(f"{channel_name},{url}\n")
                                    written_channels.add(channel_name)
                                    break
            
            # 处理"其它频道"分类
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
        
        print(f"已生成简化版TXT文件: zubo_simple.txt")
    
    except Exception as e:
        print(f"合并文件时发生错误: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("="*60)
    print("组播源处理系统")
    print("="*60)
    
    # 创建必要的目录
    os.makedirs('result_ip', exist_ok=True)
    os.makedirs('template', exist_ok=True)
    os.makedirs('output', exist_ok=True)
    
    # 检查必要的目录和文件
    for city in CITY_STREAMS:
        ip_file = f"result_ip/{city}.txt"
        template_file = f"template/{city}.txt"
        demo_file = "template/demo.txt"
        
        if not os.path.exists(ip_file):
            print(f"警告: IP文件 {ip_file} 不存在，正在创建示例文件")
            with open(ip_file, 'w', encoding='utf-8') as f:
                f.write("# IP文件格式: IP:端口\n")
                f.write("# 示例:\n")
                f.write("183.161.172.115:7000\n")
                f.write("183.164.55.78:5000\n")
                f.write("60.168.109.197:4000\n")
        
        if not os.path.exists(template_file):
            print(f"警告: 频道模板文件 {template_file} 不存在，正在创建示例模板")
            with open(template_file, 'w', encoding='utf-8') as f:
                f.write("# 频道模板文件格式\n")
                f.write("# 分类名称,#genre#\n")
                f.write("# 频道名称,http://ipipip/频道地址\n\n")
                f.write("央视频道,#genre#\n")
                f.write("CCTV1,http://ipipip/rtp/238.1.78.166:7200\n")
                f.write("CCTV2,http://ipipip/rtp/238.1.78.235:7752\n")
                f.write("卫视频道,#genre#\n")
                f.write(f"{city}卫视,http://ipipip/{CITY_STREAMS[city][0]}\n")
        
        if not os.path.exists(demo_file):
            print(f"警告: 频道分类模板文件 {demo_file} 不存在，正在创建示例模板")
            with open(demo_file, 'w', encoding='utf-8') as f:
                f.write("# 频道分类模板文件格式\n")
                f.write("# 分类名称,#genre#\n")
                f.write("# 主频道名|别名1|别名2|...\n\n")
                f.write("央视频道,#genre#\n")
                f.write("CCTV1|CCTV1-综合|CCTV-1综合|CCTV-1|\n")
                f.write("CCTV2|CCTV2-财经|CCTV-2财经|CCTV-2|\n")
                f.write("CCTV3|CCTV3-综艺|CCTV-3综艺|CCTV-3|\n")
                f.write("卫视频道,#genre#\n")
                f.write("湖南卫视|湖南卫视高清|湖南卫视HD|\n")
                f.write("浙江卫视|浙江卫视高清|浙江卫视HD|\n")
    
    # 处理每个城市
    for city_name in CITY_STREAMS:
        print(f"\n{'='*60}")
        print(f"处理城市: {city_name}")
        print(f"{'='*60}")
        
        # 第一步：从IP_Scan/result_ip/读取IP文件
        ip_list = get_ips_for_city(city_name)
        
        if not ip_list:
            print(f"{city_name} 没有可用的IP，跳过")
            continue
        
        print(f"获取到 {len(ip_list)} 个IP地址")
        
        # 第二步：读取台标文件
        logo_dict = read_logo_file()
        
        # 第三步：生成文件
        generate_files_for_city(city_name, ip_list, logo_dict)
        
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
