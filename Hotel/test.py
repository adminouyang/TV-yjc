import os
import re
import requests
import time
import concurrent.futures
import random
from datetime import datetime

# ===============================
# 配置区
# ===============================

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
]

# 搜索关键词（base64编码）
SEARCH_QUERIES = [
    "ImlwdHYvbGl2ZS96aF9jbi5qcyIgJiYgY291bnRyeT0iQ04i",  # IPTV直播
]

# IP存储目录
IP_DIR = "Hotel/ip"
if not os.path.exists(IP_DIR):
    os.makedirs(IP_DIR)

# ===============================
# IP处理函数
# ===============================

def get_isp(ip):
    """IP运营商判断"""
    # 电信IP段
    telecom_pattern = r"^(1\.|14\.|27\.|36\.|39\.|42\.|49\.|58\.|60\.|101\.|106\.|110\.|111\.|112\.|113\.|114\.|115\.|116\.|117\.|118\.|119\.|120\.|121\.|122\.|123\.|124\.|125\.|126\.|171\.|175\.|182\.|183\.|202\.|203\.|210\.|211\.|218\.|219\.|220\.|221\.|222\.)"
    # 联通IP段
    unicom_pattern = r"^(42\.1[0-9]{0,2}|43\.|58\.|59\.|60\.|61\.|110\.|111\.|112\.|113\.|114\.|115\.|116\.|117\.|118\.|119\.|120\.|121\.|122\.|123\.|124\.|125\.|126\.|171\.8[0-9]|171\.9[0-9]|171\.1[0-9]{2}|175\.|182\.|183\.|210\.|211\.|218\.|219\.|220\.|221\.|222\.)"
    # 移动IP段
    mobile_pattern = r"^(36\.|37\.|38\.|39\.1[0-9]{0,2}|42\.2|42\.3|47\.|106\.|111\.|112\.|113\.|114\.|115\.|116\.|117\.|118\.|119\.|120\.|121\.|122\.|123\.|124\.|125\.|126\.|134\.|135\.|136\.|137\.|138\.|139\.|150\.|151\.|152\.|157\.|158\.|159\.|170\.|178\.|182\.|183\.|184\.|187\.|188\.|189\.)"
    
    if re.match(telecom_pattern, ip):
        return "电信"
    elif re.match(unicom_pattern, ip):
        return "联通"
    elif re.match(mobile_pattern, ip):
        return "移动"
    else:
        return "未知"

def get_ip_info(ip_port):
    """获取IP地理信息"""
    try:
        ip = ip_port.split(":")[0]
        
        # 使用IP-API查询
        try:
            response = requests.get(f"http://ip-api.com/json/{ip}?lang=zh-CN", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    province = data.get("regionName", "未知")
                    isp = get_isp(ip)
                    return province, isp, ip_port
        except:
            pass
        
        return "未知", "未知", ip_port
        
    except Exception as e:
        return "未知", "未知", ip_port

def read_existing_ips(filepath):
    """读取现有文件内容并去重"""
    existing_ips = set()
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        match = re.match(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})', line)
                        if match:
                            existing_ips.add(match.group(1))
        except Exception as e:
            pass
    return existing_ips

def generate_fofa_urls():
    """生成FOFA搜索URL"""
    urls = []
    pages = 5
    page_size = 20
    
    for query in SEARCH_QUERIES:
        for page in range(1, pages + 1):
            url = f"https://fofa.info/result?qbase64={query}&page={page}&page_size={page_size}"
            urls.append(url)
    
    return urls

def crawl_fofa():
    """爬取FOFA数据"""
    urls = generate_fofa_urls()
    all_ips = set()
    session = requests.Session()
    
    for i, url in enumerate(urls, 1):
        print(f"📡 正在爬取第 {i}/{len(urls)} 页...")
        
        try:
            time.sleep(random.uniform(1, 3))
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            response = session.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                # 匹配IP:端口
                matches = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5})', response.text)
                for match in matches:
                    # 验证IP格式
                    ip_match = re.match(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{1,5})', match)
                    if ip_match:
                        ip_parts = ip_match.group(1).split('.')
                        if all(0 <= int(part) <= 255 for part in ip_parts):
                            all_ips.add(match)
                
                print(f"✅ 第 {i} 页获取到 {len(matches)} 个IP，当前总数 {len(all_ips)}")
            else:
                print(f"❌ 第 {i} 页请求失败，状态码: {response.status_code}")
                
        except Exception as e:
            print(f"❌ 第 {i} 页爬取失败: {e}")
    
    return all_ips

def process_and_save_ips(ip_list):
    """处理IP并保存到文件"""
    if not ip_list:
        print("⚠️ 没有获取到IP")
        return
    
    print(f"🔧 开始处理 {len(ip_list)} 个IP...")
    
    province_isp_dict = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_ip = {executor.submit(get_ip_info, ip): ip for ip in ip_list}
        
        for i, future in enumerate(concurrent.futures.as_completed(future_to_ip), 1):
            province, isp, ip_port = future.result()
            
            if province and isp and isp != "未知":
                province_clean = province.replace("省", "").replace("市", "").strip()
                if not province_clean:
                    province_clean = "未知"
                fname = f"{province_clean}{isp}.txt"
                province_isp_dict.setdefault(fname, set()).add(ip_port)
            
            if i % 50 == 0 or i == len(ip_list):
                print(f"⏳ 已处理 {i}/{len(ip_list)} 个IP...")
    
    # 保存到文件
    for fname, ips in province_isp_dict.items():
        filepath = os.path.join(IP_DIR, fname)
        existing_ips = read_existing_ips(filepath)
        new_ips = ips - existing_ips
        
        if new_ips:
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(f"\n# 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                for ip in sorted(new_ips):
                    f.write(ip + '\n')
            print(f"💾 已保存 {len(new_ips)} 个新IP到 {fname}")
    
    print(f"✅ IP处理完成！共保存到 {len(province_isp_dict)} 个分类文件")

def main():
    """主函数"""
    print("=" * 50)
    print("🌐 IP地址抓取工具")
    print(f"📁 输出目录: {IP_DIR}")
    print("=" * 50)
    
    print("\n🚀 开始爬取FOFA数据...")
    all_ips = crawl_fofa()
    
    if all_ips:
        print(f"\n🎯 总共获取到 {len(all_ips)} 个IP")
        process_and_save_ips(all_ips)
    else:
        print("❌ 没有获取到任何IP地址")
    
    print("\n" + "=" * 50)
    print("🎉 任务完成！")
    print("=" * 50)

if __name__ == "__main__":
    main()
