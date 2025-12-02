import eventlet
eventlet.monkey_patch()
import time
import datetime
from threading import Thread
import os
import re
from queue import Queue
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import json

# 配置区
FOFA_URL = "https://fofa.info/result?qbase64=ImlwdHYvbGl2ZS96aF9jbi5qcyIgJiYgY291bnRyeT0iQ04iICAmJiBwb3J0PSI5OTAxIg%3D%3D"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

IP_DIR = "Hotel/ip"

# 创建IP目录
if not os.path.exists(IP_DIR):
    os.makedirs(IP_DIR)

# 从FOFA链接获取IP信息
def fetch_ips_from_fofa():
    all_ips = []
    try:
        response = requests.get(FOFA_URL, headers=HEADERS, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 根据FOFA搜索结果页面的结构解析IP和端口
        # FOFA的结果通常在表格中显示
        ip_list = []
        
        # 方法1: 查找包含IP地址的表格
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                for cell in cells:
                    text = cell.get_text().strip()
                    # 匹配IP:端口格式
                    if re.match(r'\d+\.\d+\.\d+\.\d+:\d+', text):
                        ip_list.append(text)
        
        # 方法2: 查找所有可能包含IP的文本
        if not ip_list:
            # 使用更宽松的正则表达式匹配
            ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}:\d+\b'
            text_content = soup.get_text()
            ip_list = re.findall(ip_pattern, text_content)
        
        # 去重
        all_ips = list(set(ip_list))
        print(f"从FOFA获取到 {len(all_ips)} 个IP")
        return all_ips
    except Exception as e:
        print(f"从FOFA获取IP错误: {e}")
        # 如果网络获取失败，尝试从本地文件读取
        return read_ips_from_file()

# 从本地文件读取IP（备用方法）
def read_ips_from_file():
    # 假设有一个包含IP列表的文件
    ip_file = "ip_list.txt"
    if os.path.exists(ip_file):
        with open(ip_file, 'r', encoding='utf-8') as f:
            ips = [line.strip() for line in f if line.strip()]
        print(f"从本地文件读取到 {len(ips)} 个IP")
        return ips
    return []

# 按照省份分类保存IP
def save_ips_by_province(ips):
    province_map = {}
    for ip_port in ips:
        ip = ip_port.split(':')[0]
        # 简单的IP到省份映射（实际应该使用IP库）
        # 这里使用IP的第一个字节进行简单分类
        first_octet = int(ip.split('.')[0])
        
        # 根据中国IP地址分配进行简单分类
        if 1 <= first_octet <= 9:
            province = '北京'
        elif 10 <= first_octet <= 10:
            province = '内网'
        elif 11 <= first_octet <= 11:
            province = '北京'
        elif 12 <= first_octet <= 12:
            province = '天津'
        elif 14 <= first_octet <= 14:
            province = '山西'
        elif 27 <= first_octet <= 27:
            province = '湖南'
        elif 36 <= first_octet <= 36:
            province = '福建'
        elif 39 <= first_octet <= 39:
            province = '吉林'
        elif 42 <= first_octet <= 42:
            province = '辽宁'
        elif 49 <= first_octet <= 49:
            province = '江苏'
        elif 58 <= first_octet <= 58:
            province = '上海'
        elif 60 <= first_octet <= 60:
            province = '内蒙古'
        elif 61 <= first_octet <= 61:
            province = '黑龙江'
        elif 101 <= first_octet <= 101:
            province = '广东'
        elif 103 <= first_octet <= 103:
            province = '云南'
        elif 106 <= first_octet <= 106:
            province = '四川'
        elif 110 <= first_octet <= 110:
            province = '重庆'
        elif 111 <= first_octet <= 111:
            province = '北京'
        elif 112 <= first_octet <= 112:
            province = '江苏'
        elif 113 <= first_octet <= 113:
            province = '浙江'
        elif 114 <= first_octet <= 114:
            province = '安徽'
        elif 115 <= first_octet <= 115:
            province = '福建'
        elif 116 <= first_octet <= 116:
            province = '江西'
        elif 117 <= first_octet <= 117:
            province = '山东'
        elif 118 <= first_octet <= 118:
            province = '河南'
        elif 119 <= first_octet <= 119:
            province = '湖北'
        elif 120 <= first_octet <= 120:
            province = '湖南'
        elif 121 <= first_octet <= 121:
            province = '广东'
        elif 122 <= first_octet <= 122:
            province = '广西'
        elif 123 <= first_octet <= 123:
            province = '海南'
        elif 124 <= first_octet <= 124:
            province = '四川'
        elif 125 <= first_octet <= 125:
            province = '贵州'
        elif 126 <= first_octet <= 126:
            province = '云南'
        elif 171 <= first_octet <= 171:
            province = '陕西'
        elif 175 <= first_octet <= 175:
            province = '广东'
        elif 180 <= first_octet <= 180:
            province = '安徽'
        elif 182 <= first_octet <= 182:
            province = '四川'
        elif 183 <= first_octet <= 183:
            province = '江苏'
        elif 202 <= first_octet <= 202:
            province = '教育网'
        elif 203 <= first_octet <= 203:
            province = '香港'
        elif 210 <= first_octet <= 210:
            province = '台湾'
        else:
            province = '其他'
        
        if province not in province_map:
            province_map[province] = []
        province_map[province].append(ip_port)
    
    # 保存到文件
    for province, ip_list in province_map.items():
        filename = os.path.join(IP_DIR, f"{province}.txt")
        with open(filename, 'w', encoding='utf-8') as f:
            for ip_port in ip_list:
                f.write(f"{ip_port}\n")
        print(f"保存 {len(ip_list)} 个IP到 {filename}")

# 读取省份IP文件
def read_province_ips(province_file):
    ips = []
    try:
        with open(province_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and ':' in line:
                    ips.append(line)
        return ips
    except Exception as e:
        print(f"读取省份IP文件错误: {e}")
        return []

# 扫描单个IP
def scan_single_ip(ip_port, url_ends):
    valid_urls = []
    for url_end in url_ends:
        try:
            url = f"http://{ip_port}{url_end}"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200 and ("tsfile" in resp.text or "hls" in resp.text):
                print(f"找到有效URL: {url}")
                valid_urls.append(url)
                break  # 找到一个有效URL就停止
        except:
            continue
    return valid_urls

# 从URL提取频道信息
def extract_channels(url):
    hotel_channels = []
    try:
        # 尝试解析JSON格式
        response = requests.get(url, timeout=5)
        
        # 尝试解析为JSON
        try:
            json_data = response.json()
            if isinstance(json_data, dict) and 'data' in json_data:
                for item in json_data['data']:
                    if isinstance(item, dict):
                        name = item.get('name', '')
                        urlx = item.get('url', '')
                        if name and urlx:
                            # 构建完整的URL
                            if urlx.startswith('/'):
                                base_url = '/'.join(url.split('/')[:3])
                                full_url = base_url + urlx
                            else:
                                full_url = urlx
                            hotel_channels.append((name, full_url))
        except:
            # 如果不是JSON，尝试解析为文本格式
            text_lines = response.text.split('\n')
            for line in text_lines:
                if ',' in line and ('tsfile' in line or 'hls' in line):
                    parts = line.split(',')
                    if len(parts) >= 2:
                        name = parts[0].strip()
                        channel_url = parts[1].strip()
                        if name and channel_url:
                            hotel_channels.append((name, channel_url))
        
        return hotel_channels
    except Exception as e:
        print(f"提取频道错误 {url}: {e}")
        return []

# 测速函数
def speed_test(channels):
    if not channels:
        return []
    
    results = []
    checked = 0
    
    def test_channel(channel):
        nonlocal checked
        name, url = channel
        try:
            # 简单的连通性测试
            start_time = time.time()
            response = requests.get(url, timeout=5, stream=True)
            response.close()  # 立即关闭连接
            speed = 1.0 / (time.time() - start_time)  # 简单的速度指标
            
            checked += 1
            if checked % 10 == 0:
                print(f"已测试 {checked}/{len(channels)} 个频道")
            
            return name, url, f"{speed:.3f}"
        except:
            checked += 1
            return None
    
    # 使用线程池进行测速
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(test_channel, channel) for channel in channels]
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
    
    return results

# 规范化频道名称
def normalize_channel_name(name):
    # 移除多余的空格和特殊字符
    name = re.sub(r'\s+', ' ', name).strip()
    
    # 统一CCTV频道命名
    name = re.sub(r'CCTV[\-\s]?(\d+)', r'CCTV-\1', name)
    name = re.sub(r'中央(\d+)台', r'CCTV-\1', name)
    
    # 统一卫视命名
    name = re.sub(r'([\u4e00-\u9fa5]+)卫视', r'\1卫视', name)
    
    return name

# 处理单个省份的IP
def process_province(province_file):
    province_name = os.path.basename(province_file).replace('.txt', '')
    print(f"\n开始处理 {province_name} 的IP")
    
    # 读取该省份的所有IP
    ips = read_province_ips(province_file)
    if not ips:
        print(f"{province_name} 没有IP可处理")
        return []
    
    all_channels = []
    url_ends = [
        "/iptv/live/1000.json?key=txiptv",
        "/ZHGXTV/Public/json/live_interface.txt",
        "/iptv/live/1000.json"
    ]
    
    # 扫描IP获取有效URL
    valid_urls = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(scan_single_ip, ip, url_ends): ip for ip in ips}
        for future in as_completed(futures):
            result = future.result()
            valid_urls.extend(result)
    
    print(f"{province_name} 找到 {len(valid_urls)} 个有效URL")
    
    # 从有效URL提取频道
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(extract_channels, url): url for url in valid_urls}
        for future in as_completed(futures):
            channels = future.result()
            all_channels.extend(channels)
    
    print(f"{province_name} 提取到 {len(all_channels)} 个频道")
    
    # 对频道进行测速
    if all_channels:
        # 去重
        unique_channels = []
        seen = set()
        for channel in all_channels:
            identifier = f"{channel[0]}_{channel[1]}"
            if identifier not in seen:
                seen.add(identifier)
                unique_channels.append(channel)
        
        print(f"{province_name} 去重后剩余 {len(unique_channels)} 个频道")
        
        # 测速
        speed_results = speed_test(unique_channels)
        print(f"{province_name} 测速完成，有效频道: {len(speed_results)} 个")
        
        return speed_results
    else:
        return []

# 主函数
def main():
    print("开始获取IP列表...")
    
    # 第一步：从FOFA获取IP并按照省份分类
    ips = fetch_ips_from_fofa()
    
    if not ips:
        print("未能获取到IP，退出程序")
        return
    
    print(f"获取到 {len(ips)} 个IP，开始按省份分类...")
    save_ips_by_province(ips)
    
    # 第二步：处理每个省份的IP
    province_files = [os.path.join(IP_DIR, f) for f in os.listdir(IP_DIR) if f.endswith('.txt')]
    
    all_results = []
    for province_file in province_files:
        try:
            results = process_province(province_file)
            all_results.extend(results)
        except Exception as e:
            print(f"处理 {province_file} 时出错: {e}")
            continue
    
    print(f"\n所有省份处理完成，共获取 {len(all_results)} 个频道")
    
    if not all_results:
        print("没有获取到任何频道，退出程序")
        return
    
    # 第三步：对频道进行排序和分类
    # 按速度排序
    all_results.sort(key=lambda x: float(x[2]), reverse=True)
    
    # 保存所有频道到临时文件
    with open('all_channels.txt', 'w', encoding='utf-8') as f:
        for name, url, speed in all_results:
            f.write(f"{name},{url}\n")
    
    # 分类频道
    classify_channels('all_channels.txt', '央视.txt', "CCTV")
    classify_channels('all_channels.txt', '卫视.txt', "卫视")
    classify_channels('all_channels.txt', '地方台.txt', "都市,城市,地方")
    
    # 生成最终的M3U文件
    generate_m3u_file(all_results)
    
    # 清理临时文件
    if os.path.exists('all_channels.txt'):
        os.remove('all_channels.txt')
    
    print("任务完成！")

# 分类频道函数
def classify_channels(input_file, output_file, keywords):
    if not os.path.exists(input_file):
        print(f"输入文件 {input_file} 不存在")
        return
    
    keywords_list = keywords.split(',')
    pattern = '|'.join(keywords_list)
    
    matched_lines = []
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            if re.search(pattern, line, re.IGNORECASE):
                matched_lines.append(line)
    
    if matched_lines:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.writelines(matched_lines)
        print(f"生成 {output_file}，包含 {len(matched_lines)} 个频道")

# 生成M3U文件
def generate_m3u_file(channels):
    with open('hotel_iptv.m3u', 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for name, url, speed in channels:
            f.write(f'#EXTINF:-1,{name}\n')
            f.write(f'{url}\n')
    
    print("生成 hotel_iptv.m3u 文件")

if __name__ == "__main__":
    main()
