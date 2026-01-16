from threading import Thread
import os
import time
import datetime
from datetime import timezone, timedelta
import glob
import requests
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
import urllib3
import re
import signal
import sys

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 城市特定的测试流地址
CITY_STREAMS = {
    "安徽电信": ["udp/238.1.78.150:7072"],
    "北京市电信": ["rtp/225.1.8.21:8002"],
    "北京市联通": ["rtp/239.3.1.241:8000"],
    "江苏电信": ["udp/239.49.8.19:9614"],
    "四川电信": ["udp/239.94.0.59:5140"],
    "四川移动": ["rtp/239.11.0.78:5140"],
    "四川联通": ["rtp/239.0.0.1:5140"],
    "上海市电信": ["rtp/233.18.204.51:5140"],
    "云南电信": ["rtp/239.200.200.145:8840"],
    "内蒙古电信": ["rtp/239.29.0.2:5000"],
    "吉林电信": ["rtp/239.37.0.125:5540"],
    "天津市电信": ["rtp/239.5.1.1:5000"],
    "天津市联通": ["rtp/225.1.1.111:5002"],
    "宁夏电信": ["rtp/239.121.4.94:8538"],
    "山东电信": ["udp/239.21.1.87:5002"],
    "山东联通": ["rtp/239.253.254.78:8000"],
    "山西电信": ["udp/239.1.1.1:8001"],
    "山西联通": ["rtp/226.0.2.152:9128"],
    "广东电信": ["udp/239.77.1.19:5146"],
    "广东移动": ["rtp/239.20.0.101:2000"],
    "广东联通": ["udp/239.0.1.1:5001"],
    "广西电信": ["udp/239.81.0.107:4056"],
    "新疆电信": ["udp/238.125.3.174:5140"],
    "江西电信": ["udp/239.252.220.63:5140"],
    "河北省电信": ["rtp/239.254.200.174:6000"],
    "河南电信": ["rtp/239.16.20.21:10210"],    
    "河南联通": ["rtp/225.1.4.98:1127"],
    "浙江电信": ["udp/233.50.201.100:5140"],
    "海南电信": ["rtp/239.253.64.253:5140"],
    "湖北电信": ["rtp/239.254.96.115:8664"],
    "湖北联通": ["rtp/228.0.0.60:6108"],
    "湖南电信": ["udp/239.76.253.101:9000"],
    "甘肃电信": ["udp/239.255.30.249:8231"],
    "福建省电信": ["rtp/239.61.2.132:8708"],
    "贵州电信": ["rtp/238.255.2.1:5999"],
    "辽宁联通": ["rtp/232.0.0.126:1234"],
    "重庆市电信": ["rtp/235.254.196.249:1268"],
    "重庆市联通": ["udp/225.0.4.187:7980"],
    "陕西电信": ["rtp/239.111.205.35:5140"],
    "青海电信": ["rtp/239.120.1.64:8332"],
    "黑龙江联通": ["rtp/229.58.190.150:5000"],
}

# 配置参数
CONFIG = {
    'timeout': 3,
    'max_workers': 20,
    'result_dir': 'IP_Scan/result_ip',
    'ip_dir': 'IP_Scan/ip',
}

# 信号处理
shutdown_flag = False

def signal_handler(signum, frame):
    global shutdown_flag
    shutdown_flag = True
    print("收到停止信号，正在保存当前进度...")

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ==================== 测速模块开始 ====================

class IPManager:
    """IP管理器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.session = None
        self.stats = {
            'total_tested': 0,
            'successful': 0,
            'failed': 0,
            'cities_processed': 0
        }
        
    def get_session(self):
        """获取或创建requests session"""
        if self.session is None:
            self.session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=100,
                pool_maxsize=100
            )
            self.session.mount('http://', adapter)
            self.session.mount('https://', adapter)
        return self.session
    
    def read_ip_file(self, filepath: str):
        """读取IP文件"""
        ips = []
        if not os.path.exists(filepath):
            print(f"文件不存在: {filepath}")
            return ips
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # 移除可能的速度信息
                        ip = line.split('#')[0].strip()
                        if ':' in ip:  # 确保是IP:PORT格式
                            ips.append(ip)
        except Exception as e:
            print(f"读取文件 {filepath} 失败: {e}")
        
        return ips
    
    def write_ip_file(self, filepath: str, ips: list):
        """写入IP文件"""
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                for ip in ips:
                    f.write(f"{ip}\n")
            return True
        except Exception as e:
            print(f"写入文件 {filepath} 失败: {e}")
            return False
    
    def test_single_url(self, url: str, timeout: int = 3):
        """测试单个URL的速度"""
        try:
            start_time = time.time()
            response = requests.get(url, timeout=timeout, stream=True)
            
            if response.status_code != 200:
                return 0, f"HTTP {response.status_code}"
            
            # 下载一小段数据来计算速度
            downloaded = 0
            chunk_size = 102400
            max_size = 1024 * 1024  # 最多下载1MB
            
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    downloaded += len(chunk)
                
                if downloaded >= chunk_size * 10:  # 下载大约1000KB就够判断速度了
                    break
                
                if downloaded >= max_size:
                    break
            
            response.close()
            
            elapsed = time.time() - start_time
            if elapsed <= 0:
                return 0, "time error"
            
            speed_kbps = (downloaded / 1024) / elapsed
            return speed_kbps, ""
            
        except requests.exceptions.Timeout:
            return 0, "timeout"
        except Exception as e:
            return 0, str(e)
    
    def test_ip_with_streams(self, ip: str, streams: list):
        """测试单个IP的所有流，返回是否成功、速度和使用的流地址"""
        ip_speed = 0
        used_stream = ""
        
        for stream in streams:
            if shutdown_flag:
                break
                
            url = f"http://{ip}/{stream}"
            speed, error = self.test_single_url(url, timeout=self.config['timeout'])
            
            if error:
                print(f"{ip} 测试失败: {error} (流: {stream})")
            else:
                ip_speed = speed
                used_stream = stream
                print(f"{ip} 测试成功: {speed:.2f} KB/s (流: {stream})")
                return True, ip_speed, used_stream
        
        # 如果所有流都失败
        print(f"{ip} 所有流测试失败")
        return False, 0, ""
    
    def process_city(self, city: str, streams: list):
        """处理单个城市/运营商的测试"""
        print(f"开始处理: {city}")
        
        successful_ips = []  # 存储(ip, speed, stream)元组
        failed_ips = set()   # 存储失败的IP
        
        # 1. 首先测试上一次保存的最快IP
        result_file = os.path.join(self.config['result_dir'], f"{city}.txt")
        previous_fast_ips = self.read_ip_file(result_file)
        
        if previous_fast_ips:
            print(f"找到上一次的最快IP: {len(previous_fast_ips)} 个")
            
            # 使用多线程测试上一次的IP
            with ThreadPoolExecutor(max_workers=min(self.config['max_workers'], len(previous_fast_ips))) as executor:
                future_to_ip = {executor.submit(self.test_ip_with_streams, ip, streams): ip for ip in previous_fast_ips}
                
                for future in concurrent.futures.as_completed(future_to_ip):
                    if shutdown_flag:
                        break
                        
                    ip = future_to_ip[future]
                    try:
                        success, speed, stream = future.result()
                        self.stats['total_tested'] += 1
                        
                        if success:
                            successful_ips.append((ip, speed, stream))
                            self.stats['successful'] += 1
                            print(f"上一次的IP {ip} 仍然有效: {speed:.2f} KB/s")
                        else:
                            failed_ips.add(ip)
                            self.stats['failed'] += 1
                            print(f"上一次的IP {ip} 已失效")
                            
                    except Exception as e:
                        print(f"测试IP {ip} 时发生错误: {e}")
                        self.stats['failed'] += 1
                        failed_ips.add(ip)
        
        # 2. 如果上一次的IP不足，从原始文件中测试更多IP
        ip_file = os.path.join(self.config['ip_dir'], f"{city}.txt")
        all_ips = self.read_ip_file(ip_file)
        
        if not all_ips:
            print(f"无原始IP地址: {ip_file}")
        else:
            print(f"从原始文件读取到 {len(all_ips)} 个IP")
            
            # 排除已经测试过的IP（包括成功和失败的）
            remaining_ips = [
                ip for ip in all_ips 
                if ip not in [item[0] for item in successful_ips] 
                and ip not in failed_ips
            ]
            
            print(f"需要测试的新IP: {len(remaining_ips)} 个")
            
            if remaining_ips and not shutdown_flag:
                # 使用多线程测试剩余的IP
                with ThreadPoolExecutor(max_workers=min(self.config['max_workers'], len(remaining_ips))) as executor:
                    future_to_ip = {executor.submit(self.test_ip_with_streams, ip, streams): ip for ip in remaining_ips}
                    
                    for future in concurrent.futures.as_completed(future_to_ip):
                        if shutdown_flag:
                            break
                            
                        ip = future_to_ip[future]
                        try:
                            success, speed, stream = future.result()
                            self.stats['total_tested'] += 1
                            
                            if success:
                                successful_ips.append((ip, speed, stream))
                                self.stats['successful'] += 1
                                print(f"新IP {ip} 测试成功: {speed:.2f} KB/s")
                            else:
                                failed_ips.add(ip)
                                self.stats['failed'] += 1
                                
                        except Exception as e:
                            print(f"测试IP {ip} 时发生错误: {e}")
                            self.stats['failed'] += 1
                            failed_ips.add(ip)
        
        # 3. 从原始IP文件中删除失败的IP
        if all_ips and failed_ips:
            # 从原始IP列表中移除失败的IP
            original_count = len(all_ips)
            all_ips = [ip for ip in all_ips if ip not in failed_ips]
            remaining_count = len(all_ips)
            
            if remaining_count > 0:
                self.write_ip_file(ip_file, all_ips)
                print(f"{city} - 从原始文件中删除 {original_count - remaining_count} 个失败IP，剩余 {remaining_count} 个IP")
            else:
                # 如果所有IP都失败，保留原文件但写入注释
                self.write_ip_file(ip_file, ["# 所有IP测试失败，请检查网络或重新扫描"])
                print(f"{city} - 所有IP测试失败，文件已清空")
        
        # 4. 保存所有有效的IP到结果文件（按速度排序）
        os.makedirs(self.config['result_dir'], exist_ok=True)
        
        if successful_ips:
            # 按速度排序
            successful_ips.sort(key=lambda x: x[1], reverse=True)
            
            # 写入IP文件
            with open(result_file, 'w', encoding='utf-8') as f:
                for ip, speed, stream in successful_ips:
                    f.write(f"{ip}\n")
            
            # 记录前5个最快IP
            for i, (ip, speed, stream) in enumerate(successful_ips[:5]):
                if i == 0:
                    print(f"{city} - 最快IP: {ip} (速度: {speed:.2f} KB/s, 流: {stream})")
                elif i < 5:
                    print(f"{city} - 第{i+1}快IP: {ip} (速度: {speed:.2f} KB/s)")
            
            print(f"{city} - 结果已保存: 共 {len(successful_ips)} 个有效IP")
        else:
            with open(result_file, 'w', encoding='utf-8') as f:
                f.write(f"# {city} 无可用IP\n")
            print(f"{city} - 无可用IP，已保存空结果")
        
        self.stats['cities_processed'] += 1
        
        return {
            'city': city,
            'total_tested': len(previous_fast_ips) + (len(all_ips) if all_ips else 0),
            'valid_count': len(successful_ips),
            'best_speed': successful_ips[0][1] if successful_ips else 0
        }
    
    def print_summary(self):
        """打印统计摘要"""
        print("=" * 50)
        print("测试完成！")
        print(f"已处理城市: {self.stats['cities_processed']}")
        print(f"总测试IP数: {self.stats['total_tested']}")
        print(f"成功IP数: {self.stats['successful']}")
        print(f"失败IP数: {self.stats['failed']}")
        if self.stats['total_tested'] > 0:
            success_rate = (self.stats['successful'] / self.stats['total_tested']) * 100
            print(f"成功率: {success_rate:.1f}%")
        print("=" * 50)

def run_ip_test():
    """运行IP测速"""
    print("=" * 50)
    print("组播流IP测试工具启动")
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"配置: 超时={CONFIG['timeout']}s, 并发数={CONFIG['max_workers']}")
    print("=" * 50)
    
    # 创建管理器
    ip_manager = IPManager(CONFIG)
    
    # 确保目录存在
    os.makedirs(CONFIG['result_dir'], exist_ok=True)
    os.makedirs(CONFIG['ip_dir'], exist_ok=True)
    
    # 处理所有城市
    all_results = []
    for city, streams in CITY_STREAMS.items():
        if shutdown_flag:
            print("收到停止信号，提前结束")
            break
            
        print(f"处理城市: {city}")
        print(f"流地址: {streams}")
        
        result = ip_manager.process_city(city, streams)
        all_results.append(result)
    
    # 打印摘要
    ip_manager.print_summary()
    
    # 打印各城市结果摘要
    if all_results:
        print("\n各城市测试结果:")
        print("-" * 80)
        print(f"{'城市':<15} {'测试数':<8} {'有效数':<8} {'最快速度(KB/s)':<15}")
        print("-" * 80)
        
        for result in all_results:
            print(f"{result['city']:<15} {result['total_tested']:<8} "
                   f"{result['valid_count']:<8} {result['best_speed']:<15.2f}")
    
    print("=" * 50)
    print(f"结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

# ==================== 测速模块结束 ====================

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

def get_ips_for_city(city_name, max_ips=2):
    """从IP_Scan/result_ip/路径读取IP地址，只读取最快的2个IP"""
    # 从CITY_STREAMS中获取对应的省份/城市名称映射
    ip_file = f"IP_Scan/result_ip/{city_name}.txt"
    
    if not os.path.exists(ip_file):
        print(f"IP文件不存在: {ip_file}")
        return []
    
    ip_list = []
    try:
        with open(ip_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
            # 只取前max_ips个IP（因为文件已经是按速度排序的）
            for i, line in enumerate(lines[:max_ips]):
                cleaned_ip = clean_ip_line(line.strip())
                if cleaned_ip and ":" in cleaned_ip:
                    ip_list.append(cleaned_ip)
                    print(f"  读取第{i+1}个IP: {cleaned_ip}")
        
        print(f"从 {ip_file} 读取到 {len(ip_list)} 个最快IP地址")
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

def generate_files_for_city(city_name, ip_list, logo_dict, max_sources_per_channel=2):
    """为城市生成TXT和M3U文件，使用IP列表中最快的2个IP生成多个源"""
    if not ip_list or len(ip_list) < 1:
        print(f"{city_name} 没有可用的IP，跳过文件生成")
        return None, None
    
    # 读取频道模板
    categories = read_template_file(city_name)
    if not categories:
        print(f"{city_name} 没有频道模板，跳过文件生成")
        return None, None
    
    # 创建输出目录
    os.makedirs('output', exist_ok=True)
    
    # 生成TXT文件
    txt_file = f"output/{city_name}.txt"
    m3u_file = f"output/{city_name}.m3u"
    
    with open(txt_file, 'w', encoding='utf-8') as txt_f, \
         open(m3u_file, 'w', encoding='utf-8') as m3u_f:
        
        m3u_f.write("#EXTM3U\n")
        
        channel_count = 0
        source_count = 0
        
        for category, channels in categories:
            # 写入分类标题
            txt_f.write(f"{category},#genre#\n")
            
            for channel_name, channel_url in channels:
                # 为每个频道生成多个源，但最多使用max_sources_per_channel个IP
                used_ips = 0
                for i, ip_port in enumerate(ip_list[:max_sources_per_channel]):
                    # 替换ipipip为实际IP:端口
                    new_url = channel_url.replace("ipipip", ip_port)
                    
                    # 写入TXT文件 - 格式: 频道名称,URL$城市
                    txt_f.write(f"{channel_name},{new_url}${city_name}\n")
                    
                    # 写入M3U文件
                    # 查找台标
                    logo_url = logo_dict.get(channel_name, "")
                    
                    if logo_url:
                        m3u_f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" tvg-logo="{logo_url}" group-title="{category}",{channel_name}\n')
                    else:
                        m3u_f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" group-title="{category}",{channel_name}\n')
                    m3u_f.write(f"{new_url}\n")
                    
                    source_count += 1
                    used_ips += 1
                
                channel_count += 1
        
        print(f"  TXT文件: {txt_file} (共{channel_count}个频道，每个频道最多{min(len(ip_list), max_sources_per_channel)}个源，总计{source_count}个源)")
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
                                    f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" tvg-logo="{logo_url}" group-title="{category},{display_name}"\n')
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
    os.makedirs('IP_Scan/result_ip', exist_ok=True)
    os.makedirs('IP_Scan/ip', exist_ok=True)
    os.makedirs('template', exist_ok=True)
    os.makedirs('output', exist_ok=True)
    
    # 询问是否进行IP测速
    print("\n是否先进行IP测速？(y/n)")
    choice = input("请输入选择: ").strip().lower()
    
    if choice == 'y':
        print("\n开始IP测速...")
        run_ip_test()
        print("\nIP测速完成！")
        time.sleep(2)
    
    # 处理每个城市
    for city_name in CITY_STREAMS:
        print(f"\n{'='*60}")
        print(f"处理城市: {city_name}")
        print(f"{'='*60}")
        
        # 检查IP文件是否存在
        ip_file = f"IP_Scan/result_ip/{city_name}.txt"
        if not os.path.exists(ip_file):
            print(f"IP文件不存在: {ip_file}，跳过此城市")
            continue
        
        # 检查频道模板文件是否存在
        template_file = f"template/{city_name}.txt"
        if not os.path.exists(template_file):
            print(f"频道模板文件不存在: {template_file}，跳过此城市")
            continue
        
        # 第一步：从IP_Scan/result_ip/读取最快的2个IP
        ip_list = get_ips_for_city(city_name, max_ips=2)
        
        if not ip_list:
            print(f"{city_name} 没有可用的IP，跳过")
            continue
        
        print(f"获取到 {len(ip_list)} 个最快IP地址")
        
        # 第二步：读取台标文件
        logo_dict = read_logo_file()
        
        # 第三步：生成文件
        generate_files_for_city(city_name, ip_list, logo_dict, max_sources_per_channel=2)
        
        # 城市间延迟
        time.sleep(2)
    
    # 检查频道分类模板文件是否存在
    demo_file = "template/demo.txt"
    if not os.path.exists(demo_file):
        print(f"频道分类模板文件不存在: {demo_file}，无法进行文件合并")
        return
    
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
    try:
        main()
    except KeyboardInterrupt:
        print("程序被用户中断")
    except Exception as e:
        print(f"程序运行错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if shutdown_flag:
            print("程序已安全停止")
        sys.exit(0)
