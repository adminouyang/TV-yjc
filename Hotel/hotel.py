import eventlet
eventlet.monkey_patch()
import time
import datetime
from threading import Thread, Lock
import os
import re
from queue import Queue, Empty
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import concurrent.futures
import json
from bs4 import BeautifulSoup

# 配置区
FOFA_URLS = {
    "https://fofa.info/result?qbase64=ImlwdHYvbGl2ZS96aF9jbi5qcyIgJiYgY291bnRyeT0iQ04i": "ip.txt",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

IP_DIR = "Hotel/ip"
# 创建IP目录
if not os.path.exists(IP_DIR):
    os.makedirs(IP_DIR)
    
# IP 运营商判断
def get_isp(ip):
    # 更准确的IP段匹配
    telecom_pattern = r"^(1\.|14\.|27\.|36\.|39\.|42\.|49\.|58\.|60\.|101\.|106\.|110\.|111\.|112\.|113\.|114\.|115\.|116\.|117\.|118\.|119\.|120\.|121\.|122\.|123\.|124\.|125\.|126\.|171\.|175\.|182\.|183\.|202\.|203\.|210\.|211\.|218\.|219\.|220\.|221\.|222\.)"
    unicom_pattern = r"^(42\.1[0-9]{0,2}|43\.|58\.|59\.|60\.|61\.|110\.|111\.|112\.|113\.|114\.|115\.|116\.|117\.|118\.|119\.|120\.|121\.|122\.|123\.|124\.|125\.|126\.|171\.8[0-9]|171\.9[0-9]|171\.1[0-9]{2}|175\.|182\.|183\.|210\.|211\.|218\.|219\.|220\.|221\.|222\.)"
    mobile_pattern = r"^(36\.|37\.|38\.|39\.1[0-9]{0,2}|42\.2|42\.3|47\.|106\.|111\.|112\.|113\.|114\.|115\.|116\.|117\.|118\.|119\.|120\.|121\.|122\.|123\.|124\.|125\.|126\.|134\.|135\.|136\.|137\.|138\.|139\.|150\.|151\.|152\.|157\.|158\.|159\.|170\.|178\.|182\.|183\.|184\.|187\.|188\.|189\.)"
    
    if re.match(telecom_pattern, ip):
        return "电信"
    elif re.match(unicom_pattern, ip):
        return "联通"
    elif re.match(mobile_pattern, ip):
        return "移动"
    else:
        return "未知"

# 获取IP地理信息
def get_ip_info(ip_port):
    try:
        ip = ip_port.split(":")[0]
        # 添加重试机制
        for attempt in range(3):
            try:
                res = requests.get(f"http://ip-api.com/json/{ip}?lang=zh-CN", 
                                  timeout=10, headers=HEADERS)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("status") == "success":
                        province = data.get("regionName", "未知")
                        isp = get_isp(ip)
                        return province, isp, ip_port
                break
            except requests.RequestException:
                if attempt == 2:  # 最后一次尝试失败
                    return None, None, ip_port
                time.sleep(1)
    except Exception:
        pass
    return None, None, ip_port

# 读取现有文件内容并去重
def read_existing_ips(filepath):
    existing_ips = set()
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    ip = line.strip()
                    if ip:  # 确保不是空行
                        existing_ips.add(ip)
            print(f"📖 从 {os.path.basename(filepath)} 读取到 {len(existing_ips)} 个现有IP")
        except Exception as e:
            print(f"❌ 读取文件 {filepath} 失败: {e}")
    return existing_ips
    
# 第一阶段：爬取和分类
def first_stage():
    all_ips = set()
    
    for url, filename in FOFA_URLS.items():
        print(f"📡 正在爬取 {filename} ...")
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            # 改进的正则表达式匹配
            urls_all = re.findall(r'<a href="http://(.*?)"', r.text)
            # 过滤出有效的IP:端口格式
            all_ips.update(u.strip() for u in urls_all)
            
            print(f"✅ 从 {filename} 获取到 {len(urls_all)} 个IP，其中 {len(all_ips)} 个有效")
        except Exception as e:
            print(f"❌ 爬取失败：{e}")
        time.sleep(3)
    
    print(f"🔍 总共获取到 {len(all_ips)} 个有效IP")
    
    # 使用多线程加速IP信息查询
    province_isp_dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_ip = {executor.submit(get_ip_info, ip): ip for ip in all_ips}
        
        for future in concurrent.futures.as_completed(future_to_ip):
            province, isp, ip_port = future.result()
            if province and isp and isp != "未知":
                fname = f"{province}{isp}.txt"
                province_isp_dict.setdefault(fname, set()).add(ip_port)
    
    # 保存到文件（追加模式，不去重）
    for fname, new_ips in province_isp_dict.items():
        filepath = os.path.join(IP_DIR, fname)
        
        # 读取现有IP
        existing_ips = read_existing_ips(filepath)
        
        # 合并新旧IP并去重
        all_ips_for_file = existing_ips.union(new_ips)
        
        # 写入文件
        with open(filepath, 'w', encoding='utf-8') as f:
            for ip in all_ips_for_file:
                f.write(ip + '\n')
        
        added_count = len(all_ips_for_file) - len(existing_ips)
        print(f"💾 已更新 {fname}，新增 {added_count} 个IP，总计 {len(all_ips_for_file)} 个IP")
    
    print(f"✅ 任务完成！共处理 {len(province_isp_dict)} 个分类文件")

# 按照省份分类保存IP
def save_ips_by_province(ips):
    province_map = {}
    for ip_port in ips:
        ip = ip_port.split(':')[0]
        first_octet = ip.split('.')[0]
        if first_octet in ['1', '2']:
            province = '北京'
        elif first_octet in ['3', '4']:
            province = '上海'
        elif first_octet in ['5', '6']:
            province = '广东'
        elif first_octet in ['7', '8']:
            province = '浙江'
        else:
            province = '其他'
        
        if province not in province_map:
            province_map[province] = []
        province_map[province].append(ip_port)
    
    for province, ip_list in province_map.items():
        filename = os.path.join(IP_DIR, f"{province}.txt")
        with open(filename, 'w', encoding='utf-8') as f:
            for ip_port in ip_list:
                f.write(f"{ip_port}\n")
        print(f"保存 {len(ip_list)} 个IP到 {filename}")

# 从URL获取IP信息
def fetch_ips_from_urls():
    all_ips = []
    for url, filename in FOFA_URLS.items():
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            if 'application/json' in response.headers.get('content-type', ''):
                data = response.json()
                for item in data.get('data', []):
                    ip = item.get('ip')
                    port = item.get('port')
                    if ip and port:
                        all_ips.append(f"{ip}:{port}")
            else:
                soup = BeautifulSoup(response.text, 'html.parser')
                tables = soup.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) >= 2:
                            ip_text = cells[0].get_text().strip()
                            port_text = cells[1].get_text().strip()
                            if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip_text) and port_text.isdigit():
                                all_ips.append(f"{ip_text}:{port_text}")
        except Exception as e:
            print(f"从URL {url} 获取IP错误: {e}")
    return all_ips

# 频道分类定义
CHANNEL_CATEGORIES = {
    "央视频道": [
        "CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV4欧洲", "CCTV4美洲", "CCTV5", "CCTV5+", "CCTV6", "CCTV7",
        "CCTV8", "CCTV9", "CCTV10", "CCTV11", "CCTV12", "CCTV13", "CCTV14", "CCTV15", "CCTV16", "CCTV17",
        "兵器科技", "风云音乐", "风云足球", "风云剧场", "怀旧剧场", "第一剧场", "女性时尚", "世界地理", "央视台球", "高尔夫网球",
        "央视文化精品", "卫生健康", "电视指南", "老故事", "中学生", "发现之旅", "书法频道", "国学频道", "环球奇观"
    ],
    "卫视频道": [
        "湖南卫视", "浙江卫视", "江苏卫视", "东方卫视", "深圳卫视", "北京卫视", "广东卫视", "广西卫视", "东南卫视", "海南卫视",
        "河北卫视", "河南卫视", "湖北卫视", "江西卫视", "四川卫视", "重庆卫视", "贵州卫视", "云南卫视", "天津卫视", "安徽卫视",
        "山东卫视", "辽宁卫视", "黑龙江卫视", "吉林卫视", "内蒙古卫视", "宁夏卫视", "山西卫视", "陕西卫视", "甘肃卫视", "青海卫视",
        "新疆卫视", "西藏卫视", "三沙卫视", "兵团卫视", "延边卫视", "安多卫视", "康巴卫视", "农林卫视", "山东教育卫视",
        "中国教育1台", "中国教育2台", "中国教育3台", "中国教育4台", "早期教育"
    ],
    "数字频道": [
        "CHC动作电影", "CHC家庭影院", "CHC影迷电影", "淘电影", "淘精彩", "淘剧场", "淘4K", "淘娱乐", "淘BABY", "淘萌宠", "重温经典",
         "IPTV戏曲", "求索纪录", "求索科学",
        "求索生活", "求索动物", "纪实人文", "金鹰纪实", "纪实科教", "睛彩青少", "睛彩竞技", "睛彩篮球", "睛彩广场舞", "魅力足球", "五星体育", "体育赛事",
        "劲爆体育", "快乐垂钓", "茶频道", "先锋乒羽", "天元围棋", "汽摩", "车迷频道", "梨园频道", "文物宝库", "武术世界",
        "乐游", "生活时尚", "都市剧场", "欢笑剧场", "游戏风云", "金色学堂", "动漫秀场", "新动漫", "卡酷少儿", "金鹰卡通", "优漫卡通", "哈哈炫动", "嘉佳卡通", 
        "优优宝贝", "中国交通", "中国天气", "海看大片", "经典电影", "精彩影视", "喜剧影院", "动作影院", "精品剧场", "网络棋牌", 
    ],
    "港澳台频道": [
        "凤凰卫视中文台", "凤凰卫视资讯台", "凤凰卫视香港台", "凤凰卫视电影台", "龙祥时代","星空卫视", "CHANNEL[V]",  "","", "", "", "", "", "", "",
    ],
    "安徽频道": [
        "安徽影视", "安徽经济生活", "安徽公共", "安徽综艺体育", "安徽农业科教", "阜阳公共频道", "马鞍山新闻综合", "马鞍山公共", "", "", "", "环球奇观",
        "临泉一台", "", "", "", "", "", "", "",
        "", "", "", "", "", "", "", "", "", "", "",
    ],
    "上海频道": [
        "新闻综合", "都市频道", "东方影视", "纪实人文", "第一财经", "五星体育", "东方财经", "ICS频道", "上海教育台", "七彩戏剧", "法治天地", "金色学堂",
        "动漫秀场", "欢笑剧场4K", "生活时尚", "", "", "", "", "",
        "", "", "", "", "", "", "", "", "", "", "",
    ],
    "湖南频道": [
        "湖南国际", "湖南电影", "湖南电视剧", "湖南经视", "湖南娱乐", "湖南公共", "湖南都市","湖南教育", "芒果互娱", "长沙新闻", "长沙政法", "长沙影视", "长沙女性", "",
        "益阳公共", "抗战剧场", "古装剧场", "高清院线", "先锋兵羽", "", "", "",
        "", "", "", "", "", "", "", "", "", "", "",
    ],
    "湖北频道": [
        "湖北综合", "湖北影视", "湖北生活", "湖北教育", "湖北经视", "荆州新闻", "荆州垄上", "", "","", "", "", "", "", "", "",
    ],
    "山东频道": [
         "山东综艺", "烟台新闻","", "", "", "", "", "", "",
    ],
    "广东频道": [
        "", "", "", "", "", "", "广东科教", "广东体育", "广州", "广东珠江","嘉佳卡通", "茂名综合", "", "", "", "", "",
    ],
    "广西频道": [
        "广西影视", "广西综艺", "广西都市", "广西新闻", "广西移动", "广西科技", "精彩影视", "平南台", "南宁影视", "玉林新闻综合","", "", "", "", "", "", "",
    ],
    "四川频道": [
        "", "", "", "", "", "", "", "", "蓬安电视台", "","", "", "", "", "", "", "",
    ],
    "新疆频道": [
        "新疆2", "新疆3", "新疆4", "新疆5", "新疆6", "新疆7", "新疆8", "新疆9", "", "","", "", "", "", "", "", "",
    ],
}

# 特殊符号映射，在匹配时将特殊符号替换为空
SPECIAL_SYMBOLS = ["HD", "LT", "高清", "标清", "超清", "4K", "4k", "H265", "H264", "H.265", "H.264", 
                   "HEVC", "AVC", "1080P", "720P", "576P", "480P", "360P", "杜比", "Dolby", 
                   "环绕", "立体声", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", 
                   "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", 
                   "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", 
                   "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", 
                   "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", 
                   "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", 
                   "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", 
                   "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", 
                   "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", 
                   "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", 
                   "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", 
                   "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", 
                   "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", 
                   "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", 
                   "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", 
                   "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", 
                   "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", 
                   "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道", "声道"]

# 移除特殊符号的函数
def remove_special_symbols(text):
    """移除频道名称中的特殊符号"""
    for symbol in SPECIAL_SYMBOLS:
        text = text.replace(symbol, "")
    return text.strip()

# 改进的频道名称映射，使用精确匹配
CHANNEL_MAPPING = {
    "CCTV1": ["CCTV1", "CCTV-1", "CCTV1综合", "CCTV1高清", "CCTV1HD", "cctv1"],
    "CCTV2": ["CCTV2", "CCTV-2", "CCTV2财经", "CCTV2高清", "CCTV2HD", "cctv2"],
    "CCTV3": ["CCTV3", "CCTV-3", "CCTV3综艺", "CCTV3高清", "CCTV3HD", "cctv3"],
    "CCTV4": ["CCTV4", "CCTV-4", "CCTV4中文国际", "CCTV4高清", "CCTV4HD", "cctv4"],
    "CCTV5": ["CCTV5", "CCTV-5", "CCTV5体育", "CCTV5高清", "CCTV5HD", "cctv5"],
    "CCTV5+": ["CCTV5+", "CCTV-5+", "CCTV5+体育赛事", "CCTV5+高清", "CCTV5+HD", "cctv5+", "CCTV5plus"],
    "CCTV6": ["CCTV6", "CCTV-6", "CCTV6电影", "CCTV6高清", "CCTV6HD", "cctv6"],
    "CCTV7": ["CCTV7", "CCTV-7", "CCTV7军事", "CCTV7高清", "CCTV7HD", "cctv7"],
    "CCTV8": ["CCTV8", "CCTV-8", "CCTV8电视剧", "CCTV8高清", "CCTV8HD", "cctv8"],
    "CCTV9": ["CCTV9", "CCTV-9", "CCTV9纪录", "CCTV9高清", "CCTV9HD", "cctv9"],
    "CCTV10": ["CCTV10", "CCTV-10", "CCTV10科教", "CCTV10高清", "CCTV10HD", "cctv10"],
    "CCTV11": ["CCTV11", "CCTV-11", "CCTV11戏曲", "CCTV11高清", "CCTV11HD", "cctv11"],
    "CCTV12": ["CCTV12", "CCTV-12", "CCTV12社会与法", "CCTV12高清", "CCTV12HD", "cctv12"],
    "CCTV13": ["CCTV13", "CCTV-13", "CCTV13新闻", "CCTV13高清", "CCTV13HD", "cctv13"],
    "CCTV14": ["CCTV14", "CCTV-14", "CCTV14少儿", "CCTV14高清", "CCTV14HD", "cctv14"],
    "CCTV15": ["CCTV15", "CCTV-15", "CCTV15音乐", "CCTV15高清", "CCTV15HD", "cctv15"],
    "CCTV16": ["CCTV16", "CCTV-16", "CCTV16奥林匹克", "CCTV16高清", "CCTV16HD", "cctv16"],
    "CCTV17": ["CCTV17", "CCTV-17", "CCTV17农业农村", "CCTV17高清", "CCTV17HD", "cctv17"],
    
    "CCTV4欧洲": ["CCTV4欧洲", "CCTV-4欧洲", "CCTV4欧洲高清", "CCTV4欧洲HD"],
    "CCTV4美洲": ["CCTV4美洲", "CCTV-4美洲", "CCTV4美洲高清", "CCTV4美洲HD"],
    
    "兵器科技": ["兵器科技", "CCTV兵器科技", "兵器科技频道"],
    "风云音乐": ["风云音乐", "CCTV风云音乐"],
    "第一剧场": ["第一剧场", "CCTV第一剧场"],
    "风云足球": ["风云足球", "CCTV风云足球"],
    "风云剧场": ["风云剧场", "CCTV风云剧场"],
    "怀旧剧场": ["怀旧剧场", "CCTV怀旧剧场"],
    "女性时尚": ["女性时尚", "CCTV女性时尚"],
    "世界地理": ["世界地理", "CCTV世界地理"],
    "央视台球": ["央视台球", "CCTV央视台球"],
    "高尔夫网球": ["高尔夫网球", "央视高网", "CCTV高尔夫网球"],
    "央视文化精品": ["央视文化精品", "CCTV央视文化精品"],
    "卫生健康": ["卫生健康", "CCTV卫生健康"],
    "电视指南": ["电视指南", "CCTV电视指南"],
    "东南卫视": ["福建东南", "东南卫视"],
    "东方卫视": ["上海卫视", "东方卫视"],
    "农林卫视": ["陕西农林卫视", "农林卫视"],
    "江西卫视": ["江西卫视"],
    "黑龙江卫视": ["黑龙江卫视"],
    "吉林卫视": ["吉林卫视"],
    "甘肃卫视": ["甘肃卫视"],
    "湖南卫视": ["湖南卫视"],
    "河南卫视": ["河南卫视"],
    "河北卫视": ["河北卫视"],
    "湖北卫视": ["湖北卫视"],
    "重庆卫视": ["重庆卫视"],
    "广西卫视": ["广西卫视"],
    "天津卫视": ["天津卫视"],
    "山东卫视": ["山东卫视"],
    "星空卫视": ["星空卫视", "星空衛視", "XF星空卫视"],
    "四川卫视": ["四川卫视"],
    "贵州卫视": ["贵州卫视"],
    "南方卫视": ["南方卫视"],
    "内蒙古卫视": ["内蒙古卫视", "内蒙古", "内蒙卫视"],
    "康巴卫视": ["康巴卫视"],
    "山东教育卫视": ["山东教育", "山东教育卫视"],
    "新疆卫视": ["新疆卫视", "新疆1"],
    "西藏卫视": ["西藏卫视", "XZTV2"],
    
    "中国教育1台": ["CETV1", "中国教育1台", "中国教育一台"],
    "中国教育2台": ["CETV2", "中国教育2台", "中国教育二台"],
    "中国教育3台": ["CETV3", "中国教育3台", "中国教育三台"],
    "中国教育4台": ["CETV4", "中国教育4台", "中国教育四台"],
    
    "CHC动作电影": ["CHC动作电影"],
    "CHC家庭影院": ["CHC家庭影院"],
    "CHC影迷电影": ["CHC影迷电影"],
    
    "淘电影": ["淘电影", "IPTV淘电影"],
    "淘精彩": ["淘精彩", "IPTV淘精彩"],
    "淘剧场": ["淘剧场", "IPTV淘剧场"],
    "淘4K": ["淘4K", "IPTV淘4K"],
    "淘娱乐": ["淘娱乐", "IPTV淘娱乐"],
    "淘BABY": ["淘BABY", "IPTV淘BABY", "淘baby"],
    "淘萌宠": ["淘萌宠", "IPTV淘萌宠"],
    
    "魅力足球": ["魅力足球", "上海魅力足球"],
    "睛彩青少": ["睛彩青少", "睛彩羽毛球"],
    "求索纪录": ["求索纪录", "求索记录"],
    "金鹰纪实": ["金鹰纪实", "金鹰记实"],
    "纪实科教": ["纪实科教", "北京纪实科教"],
    "星空卫视": ["星空卫视", "星空衛視"],
    "CHANNEL[V]": ["Channel[V]", "CHANNEL[V]"],
    "凤凰卫视中文台": ["凤凰卫视中文台", "凤凰中文", "凤凰卫视"],
    "凤凰卫视香港台": ["凤凰卫视香港台", "凤凰香港"],
    "凤凰卫视资讯台": ["凤凰卫视资讯台", "凤凰资讯", "凤凰咨询"],
    "凤凰卫视电影台": ["凤凰卫视电影台", "凤凰电影", "鳳凰衛視電影台"],
    
    "茶频道": ["茶频道", "湖南茶频道"],
    "快乐垂钓": ["快乐垂钓"],
    "先锋乒羽": ["先锋乒羽"],
    "天元围棋": ["天元围棋"],
    "书法频道": ["书法频道", "书法书画"],
    "环球奇观": ["环球奇观", "环球旅游", "安广网络"],
    "中学生": ["中学生", "中学生课堂"],
    "安徽综艺体育": ["安徽综艺体育", "安徽综艺"],
    "安徽农业科教": ["安徽农业科教", "安徽科教"],
    "马鞍山新闻综合": ["马鞍山新闻综合", "马鞍山新闻"],
    "欢笑剧场4K": ["欢笑剧场4K", "欢笑剧场"],
    "广东珠江": ["广东珠江", "珠江台"],
    "广东科教": ["广东科教", "广东科教高清电信"],
    "广州": ["广州", "XF广州台"],
    "嘉佳卡通": ["嘉佳卡通", "广东嘉佳卡通", "佳佳卡通"],
    "茂名综合": ["茂名综合", "茂名综合高清"],
    "广西影视": ["广西影视"],
    "广西综艺": ["广西综艺"],
    "广西新闻": ["广西新闻"],
    "广西都市": ["广西都市"],
    "玉林新闻综合": ["玉林新闻综合", "XF玉林台"],
    "龙祥时代": ["龙祥时代", "XF有线电影"],
    "汽摩": ["汽摩", "汽摩频道", "重庆汽摩"],
    "梨园频道": ["梨园频道", "梨园", "河南梨园"],
    "文物宝库": ["文物宝库", "河南文物宝库"],
    "武术世界": ["武术世界", "河南武术世界"],
    "乐游": ["乐游", "乐游频道", "乐游纪实"],
    "欢笑剧场": ["欢笑剧场", "上海欢笑剧场"],
    "生活时尚": ["生活时尚", "SiTV生活时尚", "上海生活时尚"],
    "都市剧场": ["都市剧场", "SiTV都市剧场", "上海都市剧场"],
    "游戏风云": ["游戏风云", "SiTV游戏风云", "上海游戏风云"],
    "金色学堂": ["金色学堂", "SiTV金色学堂", "上海金色学堂"],
    "动漫秀场": ["动漫秀场", "SiTV动漫秀场", "上海动漫秀场"],
    "卡酷少儿": ["卡酷少儿", "卡酷动画", "卡酷动漫", "北京卡酷"],
    "哈哈炫动": ["哈哈炫动", "炫动卡通"],
    "优漫卡通": ["优漫卡通", "优漫漫画"],
    "金鹰卡通": ["金鹰卡通", "湖南金鹰卡通"],
    "中国交通": ["中国交通", "中国交通频道"],
    "中国天气": ["中国天气", "中国天气频道"],
    "经典电影": ["经典电影", "IPTV经典电影"],
    "精彩影视": ["精彩影视", "IPTV精彩影视"],
    "喜剧影院": ["喜剧影院", "IPTV喜剧影院"],
    "动作影院": ["动作影院", "IPTV动作影院"],
    "精品剧场": ["精品剧场", "IPTV精品剧场"],
    "网络棋牌": ["网络棋牌", "IPTV网络棋牌"],
}

RESULTS_PER_CHANNEL = 20

# 读取台标文件
def read_logo_file():
    logo_dict = {}
    logo_file = "Hotel/logo.txt"
    if os.path.exists(logo_file):
        try:
            with open(logo_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and ',' in line:
                        parts = line.split(',', 1)
                        channel_name = parts[0].strip()
                        logo_url = parts[1].strip()
                        logo_dict[channel_name] = logo_url
        except Exception as e:
            print(f"读取台标文件错误: {e}")
    return logo_dict

# 检测IP:端口可用性
def check_ip_availability(ip_port, timeout=2):
    """检测IP:端口是否可用"""
    try:
        # 尝试连接HTTP服务
        test_urls = [
            f"http://{ip_port}/",
            f"http://{ip_port}/iptv/live/1000.json?key=txiptv",
            f"http://{ip_port}/ZHGXTV/Public/json/live_interface.txt"
        ]
        
        for url in test_urls:
            try:
                response = requests.get(url, timeout=timeout, headers=HEADERS)
                if response.status_code == 200:
                    return True
            except:
                continue
                
        return False
    except Exception as e:
        return False

# 批量检测IP可用性并更新文件
def check_and_update_ip_file(province_file):
    """检测IP可用性并更新文件"""
    print(f"\n开始检测 {province_file} 中的IP可用性...")
    
    available_ips = []
    all_ips = []
    
    # 读取IP文件
    try:
        with open(province_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    all_ips.append(line)
    except Exception as e:
        print(f"读取IP文件错误: {e}")
        return
    
    total_ips = len(all_ips)
    print(f"需要检测 {total_ips} 个IP")
    
    # 使用线程池并行检测
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = {}
        for ip_port in all_ips:
            future = executor.submit(check_ip_availability, ip_port)
            futures[future] = ip_port
        
        completed = 0
        for future in as_completed(futures):
            ip_port = futures[future]
            try:
                is_available = future.result()
                completed += 1
                
                if is_available:
                    available_ips.append(ip_port)
                    print(f"✓ {ip_port} 可用 ({completed}/{total_ips})")
                else:
                    print(f"✗ {ip_port} 不可用 ({completed}/{total_ips})")
                    
                # 每检测10个IP显示一次进度
                if completed % 10 == 0 or completed == total_ips:
                    print(f"进度: {completed}/{total_ips} ({completed/total_ips*100:.1f}%) - 可用: {len(available_ips)} 个")
                    
            except Exception as e:
                completed += 1
                print(f"✗ {ip_port} 检测失败 ({completed}/{total_ips})")
    
    # 更新IP文件，只保留可用的IP
    if available_ips:
        with open(province_file, 'w', encoding='utf-8') as f:
            for ip_port in available_ips:
                f.write(f"{ip_port}\n")
        
        print(f"\n✓ 已更新 {province_file}")
        print(f"  原始IP数量: {total_ips}")
        print(f"  可用IP数量: {len(available_ips)}")
        print(f"  不可用IP已删除: {total_ips - len(available_ips)}")
    else:
        print(f"\n✗ 没有可用的IP，文件 {province_file} 将保持不变")
    
    return available_ips

# 读取文件并设置参数
def read_config(config_file):
    ip_configs = []
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if ':' in line:
                        ip_part, port = line.split(':', 1)
                        a, b, c, d = ip_part.split('.')
                        ip = f"{a}.{b}.{c}.1"
                        ip_configs.append((ip, port))
        return ip_configs
    except Exception as e:
        print(f"读取文件错误: {e}")
        return []

# 发送get请求检测url是否可访问
def check_ip_port(ip_port, url_end):
    try:
        url = f"http://{ip_port}{url_end}"
        resp = requests.get(url, timeout=2)
        resp.raise_for_status()
        if "tsfile" in resp.text or "hls" in resp.text:
            print(f"{url} 访问成功")
            return url
    except:
        return None

# 多线程检测url，获取有效ip_port
def scan_ip_port(ip, port, url_end):
    valid_urls = []
    a, b, c, d = map(int, ip.split('.'))
    ip_ports = [f"{a}.{b}.{c}.{x}:{port}" for x in range(1, 256)]
    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(check_ip_port, ip_port, url_end): ip_port for ip_port in ip_ports}
        for future in as_completed(futures):
            result = future.result()
            if result:
                valid_urls.append(result)
    return valid_urls    

# 发送GET请求获取JSON文件, 解析JSON文件, 获取频道信息
def extract_channels(url):
    hotel_channels = []
    try:
        json_url = f"{url}"
        urls = url.split('/', 3)
        url_x = f"{urls[0]}//{urls[2]}"
        if "iptv" in json_url:
            response = requests.get(json_url, timeout=2)
            json_data = response.json()
            for item in json_data['data']:
                if isinstance(item, dict):
                    name = item.get('name')
                    urlx = item.get('url')
                    if "tsfile" in urlx:
                        urld = f"{url_x}{urlx}"
                        hotel_channels.append((name, urld))
        elif "ZHGXTV" in json_url:
            response = requests.get(json_url, timeout=2)
            json_data = response.content.decode('utf-8')
            data_lines = json_data.split('\n')
            for line in data_lines:
                if "," in line and "hls" in line:
                    name, channel_url = line.strip().split(',')
                    parts = channel_url.split('/', 3)
                    if len(parts) >= 4:
                        urld = f"{url_x}/{parts[3]}"
                        hotel_channels.append((name, urld))
        return hotel_channels
    except Exception:
        return []

# 测速
def speed_test(channels):
    def show_progress():
        while checked[0] < len(channels):
            numberx = checked[0] / len(channels) * 100
            print(f"已测试{checked[0]}/{len(channels)}，可用频道:{len(results)}个，进度:{numberx:.2f}%")
            time.sleep(5)
    
    def worker():
        while True:
            try:
                channel_name, channel_url = task_queue.get()
                try:
                    channel_url_t = channel_url.rstrip(channel_url.split('/')[-1])
                    lines = requests.get(channel_url, timeout=2).text.strip().split('\n')
                    ts_lists = [line.split('/')[-1] for line in lines if line.startswith('#') == False]
                    if ts_lists:
                        ts_url = channel_url_t + ts_lists[0]
                        ts_lists_0 = ts_lists[0].rstrip(ts_lists[0].split('.ts')[-1])
                        with eventlet.Timeout(5, False):
                            start_time = time.time()
                            cont = requests.get(ts_url, timeout=2).content
                            resp_time = (time.time() - start_time) * 1                    
                        if cont and resp_time > 0:
                            checked[0] += 1
                            temp_filename = f"temp_{hash(channel_url)}.ts"
                            with open(temp_filename, 'wb') as f:
                                f.write(cont)
                            normalized_speed = len(cont) / resp_time / 1024 / 1024
                            os.remove(temp_filename)
                            # 过滤掉速度过慢的频道（≤0.001 MB/s）
                            if normalized_speed > 0.001:
                                result = channel_name, channel_url, f"{normalized_speed:.3f}"
                                print(f"✓ {channel_name}, {channel_url}: {normalized_speed:.3f} MB/s")
                                results.append(result)
                            else:
                                print(f"× {channel_name}, {channel_url}: 速度过慢 ({normalized_speed:.3f} MB/s)，已过滤")
                        else:
                            checked[0] += 1
                except Exception as e:
                    checked[0] += 1
            except:
                checked[0] += 1
            finally:
                task_queue.task_done()
    
    task_queue = Queue()
    results = []
    checked = [0]
    
    Thread(target=show_progress, daemon=True).start()
    
    for _ in range(min(10, len(channels))):
        Thread(target=worker, daemon=True).start()
    
    for channel in channels:
        task_queue.put(channel)
    
    task_queue.join()
    return results

# 统一频道名称 - 改进版本，移除特殊符号后再匹配
def unify_channel_name(channels_list):
    new_channels_list = []
    
    for name, channel_url, speed in channels_list:
        original_name = name
        unified_name = None
        
        # 清理名称，移除特殊符号
        clean_name = remove_special_symbols(name.strip())
        
        # 首先尝试精确匹配
        for standard_name, variants in CHANNEL_MAPPING.items():
            for variant in variants:
                # 移除variant中的特殊符号
                clean_variant = remove_special_symbols(variant)
                
                # 进行匹配
                if clean_variant and clean_variant.lower() in clean_name.lower():
                    unified_name = standard_name
                    break
                # 如果clean_name包含variant
                elif variant and variant.lower() in clean_name.lower():
                    unified_name = standard_name
                    break
            if unified_name:
                break
        
        # 如果没有找到映射，则尝试部分匹配
        if not unified_name:
            for standard_name, variants in CHANNEL_MAPPING.items():
                for variant in variants:
                    clean_variant = remove_special_symbols(variant)
                    # 检查是否有共同的部分
                    if clean_variant and len(clean_variant) > 2:
                        # 分割成单词
                        variant_words = re.findall(r'[a-zA-Z0-9\u4e00-\u9fa5]+', clean_variant.lower())
                        clean_words = re.findall(r'[a-zA-Z0-9\u4e00-\u9fa5]+', clean_name.lower())
                        
                        # 检查是否有足够的匹配
                        match_count = 0
                        for v_word in variant_words:
                            for c_word in clean_words:
                                if v_word in c_word or c_word in v_word:
                                    match_count += 1
                                    break
                        
                        # 如果匹配的单词数超过一半
                        if match_count >= len(variant_words) / 2 and match_count > 0:
                            unified_name = standard_name
                            break
                if unified_name:
                    break
        
        # 如果还是没有找到映射，则保留原名称
        if not unified_name:
            unified_name = original_name
        
        new_channels_list.append(f"{unified_name},{channel_url},{speed}\n")
        if original_name != unified_name:
            print(f"频道名称统一: '{original_name}' -> '{unified_name}' (清理后: '{clean_name}')")
    
    return new_channels_list

# 定义排序函数
def channel_key(channel_name):
    match = re.search(r'\d+', channel_name)
    return int(match.group()) if match else float('inf')

# 分类频道
def classify_channels_by_category(channels_data):
    categorized_channels = {}
    
    # 初始化分类字典
    for category in CHANNEL_CATEGORIES.keys():
        categorized_channels[category] = []
    
    # 添加"其他"分类
    categorized_channels["其他频道"] = []
    
    for line in channels_data:
        try:
            parts = line.strip().split(',')
            if len(parts) < 2:
                continue
            name = parts[0]
            url = parts[1]
            speed = parts[2] if len(parts) > 2 else "0.000"
            assigned = False
            
            # 查找所属分类
            for category, channel_list in CHANNEL_CATEGORIES.items():
                if name in channel_list:
                    categorized_channels[category].append((name, url, speed))
                    assigned = True
                    break
            
            # 如果未分配到任何分类，则放入"其他"
            if not assigned:
                categorized_channels["其他频道"].append((name, url, speed))
        except Exception as e:
            print(f"分类频道时出错: {e}, 行: {line}")
            continue
    
    return categorized_channels

# 生成M3U文件
def generate_m3u_file(txt_file_path, m3u_file_path):
    """从txt文件生成m3u文件"""
    print(f"开始生成M3U文件: {m3u_file_path}")
    
    # 读取台标文件
    logo_dict = read_logo_file()
    
    # EPG链接
    epg_url = "https://gh.catmak.name/https://raw.githubusercontent.com/Guovin/iptv-api/refs/heads/master/output/epg/epg.gz"
    
    with open(m3u_file_path, 'w', encoding='utf-8') as m3u_file:
        # 写入M3U头部
        m3u_file.write(f'#EXTM3U x-tvg-url="{epg_url}"\n')
        
        # 读取txt文件
        with open(txt_file_path, 'r', encoding='utf-8') as txt_file:
            current_group = ""
            
            for line in txt_file:
                line = line.strip()
                if not line:
                    continue
                
                # 检查是否是分组行
                if line.endswith(',#genre#'):
                    current_group = line.replace(',#genre#', '')
                    continue
                
                # 处理频道行
                if ',' in line and not line.startswith('#'):
                    try:
                        parts = line.split(',')
                        if len(parts) >= 2:
                            channel_name = parts[0]
                            channel_url = parts[1]
                            
                            # 获取台标
                            logo_url = logo_dict.get(channel_name, "")
                            
                            # 写入M3U条目
                            m3u_file.write(f'#EXTINF:-1 tvg-name="{channel_name}" tvg-logo="{logo_url}" group-title="{current_group}",{channel_name}\n')
                            m3u_file.write(f'{channel_url}\n')
                    except Exception as e:
                        print(f"处理频道行错误: {line}, 错误: {e}")
    
    print(f"M3U文件已生成: {m3u_file_path}")

# 获取酒店源流程        
def hotel_iptv(config_file):
    # 先检测并更新IP文件
    available_ips = check_and_update_ip_file(config_file)
    
    if not available_ips:
        print(f"没有可用的IP，跳过 {config_file}")
        return
    
    ip_configs = set(read_config(config_file))
    valid_urls = []
    channels = []
    configs = []
    url_ends = ["/iptv/live/1000.json?key=txiptv", "/ZHGXTV/Public/json/live_interface.txt"]
    
    for url_end in url_ends:
        for ip, port in ip_configs:
            configs.append((ip, port, url_end))
    
    for ip, port, url_end in configs:
        valid_urls.extend(scan_ip_port(ip, port, url_end))
    
    print(f"扫描完成，获取有效url共：{len(valid_urls)}个")
    
    for valid_url in valid_urls:
        channels.extend(extract_channels(valid_url))
    
    print(f"共获取频道：{len(channels)}个\n开始测速")
    results = speed_test(channels)
    
    # 对频道进行排序
    results.sort(key=lambda x: -float(x[2]))
    results.sort(key=lambda x: channel_key(x[0]))
    
    # 统一频道名称
    unified_channels = unify_channel_name(results)
    
    # 写入原始数据文件
    with open('1.txt', 'a', encoding='utf-8') as f:
        for line in unified_channels:
            f.write(line.split(',')[0] + ',' + line.split(',')[1] + '\n')
    print("测速完成")

# 主函数
def main():
    # 显示脚本开始时间
    start_time = datetime.datetime.now()
    print(f"脚本开始运行时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)")
    
    # 第一步：获取IP并按照省份分类
    print("\n开始获取IP列表...")
    ips = fetch_ips_from_urls()
    print(f"获取到 {len(ips)} 个IP")
    
    # 保存IP到省份文件
    save_ips_by_province(ips)
    
    # 第二步：处理每个省份的IP
    province_files = [f for f in os.listdir(IP_DIR) if f.endswith('.txt')]
    
    for province_file in province_files:
        province_name = province_file.replace('.txt', '')
        print(f"\n处理 {province_name} 的IP...")
        
        config_file = os.path.join(IP_DIR, province_file)
        hotel_iptv(config_file)
    
    # 第三步：读取统一后的频道数据并进行分类
    if not os.path.exists('1.txt'):
        print("没有找到频道数据文件")
        return
    
    with open('1.txt', 'r', encoding='utf-8') as f:
        raw_lines = f.readlines()
    
    # 转换为(channel, url, speed)格式
    channels_data = []
    for line in raw_lines:
        if ',' in line and line.strip():
            parts = line.strip().split(',')
            if len(parts) >= 2:
                name = parts[0]
                url = parts[1]
                speed = parts[2] if len(parts) > 2 else "0.000"
                channels_data.append(f"{name},{url},{speed}")
    
    # 对数据进行分类
    categorized = classify_channels_by_category(channels_data)
    
    # 写入分类文件
    file_paths = []
    for category, channels in categorized.items():
        if channels:
            # 对每个分类内的频道进行排序
            channels.sort(key=lambda x: channel_key(x[0]))
            
            # 限制每个频道的结果数量
            channel_count = {}
            filtered_channels = []
            
            for name, url, speed in channels:
                if name not in channel_count:
                    channel_count[name] = 0
                
                if channel_count[name] < RESULTS_PER_CHANNEL:
                    filtered_channels.append((name, url, speed))
                    channel_count[name] += 1
            
            # 按照速度排序
            filtered_channels.sort(key=lambda x: -float(x[2]))
            
            # 写入文件
            filename = f"{category.replace('频道', '')}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"{category},#genre#\n")
                for name, url, speed in filtered_channels:
                    f.write(f"{name},{url}\n")
            
            file_paths.append(filename)
            print(f"已保存 {len(filtered_channels)} 个频道到 {filename}")
    
    # 合并写入文件
    file_contents = []
    
    for file_path in file_paths:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding="utf-8") as f:
                content = f.read()
                file_contents.append(content)
    
    # 获取北京时间
    beijing_time = datetime.datetime.now()
    current_time = beijing_time.strftime("%Y/%m/%d %H:%M")
    
    with open("1.txt", "w", encoding="utf-8") as f:
        f.write(f"{current_time}更新,#genre#\n")
        f.write(f"浙江卫视,http://ali-m-l.cztv.com/channels/lantian/channel001/1080p.m3u8\n")
        for content in file_contents:
            f.write(f"\n{content}")
    
    # 原始顺序去重
    with open('1.txt', 'r', encoding="utf-8") as f:
        lines = f.readlines()
    
    unique_lines = [] 
    seen_lines = set() 
    for line in lines:
        if line not in seen_lines:
            unique_lines.append(line)
            seen_lines.add(line)
    
    # 确保输出目录存在
    output_dir = "Hotel"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 写入txt文件
    txt_output_path = 'Hotel/iptv.txt'
    with open(txt_output_path, 'w', encoding="utf-8") as f:
        f.writelines(unique_lines)
    
    # 生成M3U文件
    m3u_output_path = 'Hotel/iptv.m3u'
    generate_m3u_file(txt_output_path, m3u_output_path)
    
    # 移除过程文件
    files_to_remove = ["1.txt"] + file_paths
    for file in files_to_remove:
        if os.path.exists(file):
            os.remove(file)
    
    # 显示脚本结束时间
    end_time = datetime.datetime.now()
    print(f"\n脚本结束运行时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)")
    
    # 计算运行时间
    run_time = end_time - start_time
    hours, remainder = divmod(run_time.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    print(f"总运行时间: {hours}小时{minutes}分{seconds}秒")
    print("任务运行完毕，所有频道合并到iptv.txt和iptv.m3u")

if __name__ == "__main__":
    print("🚀 开始IP爬取和分类...")
    print(f"📁 结果将保存到 {IP_DIR} 目录")
    first_stage()
    main()
