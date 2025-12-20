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
    "北京市电信": ["rtp/225.1.8.21:8002"],
    "北京市联通": ["rtp/239.3.1.241:8000"],
    "江苏电信": ["udp/239.49.8.19:9614"],
    "四川电信": ["udp/239.93.0.169:5140"],
}

# 频道分类模板 - 按照您提供的顺序
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
        "凤凰卫视中文台", "凤凰卫视资讯台", "凤凰卫视香港台", "凤凰卫视电影台", "龙祥时代", "星空卫视", "CHANNEL[V]", "", "", "", "", "", "", "", "",
    ],
    "安徽频道": [
        "安徽影视", "安徽经济生活", "安徽公共", "安徽综艺体育", "安徽农业科教", "阜阳公共频道", "马鞍山新闻综合", "马鞍山公共", "", "", "", "环球奇观",
        "肥西新闻综合","黄山新闻综合","黄山文旅频道","旌德新闻综合","霍邱新闻综合","六安综合频道","六安社会生活","淮北新闻综合","淮北经济生活","淮南新闻综合","淮南民生频道",
        "滁州新闻综合","滁州科教频道","滁州公共频道","蒙城新闻频道","南陵新闻综合","祁门综合频道","湾沚综合频道","繁昌新闻综合","桐城综合频道","太湖新闻综合","池州新闻综合","池州文教生活",
        "义安新闻综合","阜阳新闻综合","阜阳生活频道","阜阳教育频道","阜阳都市文艺","泗县新闻频道","临泉新闻频道","阜南新闻综合","亳州综合频道","亳州农村频道","徽州新闻频道""蚌埠新闻综合",
        "蚌埠生活频道","寿县新闻综合","屯溪融媒频道","芜湖新闻综合","芜湖生活频道","无为新闻频道","马鞍山新闻综合","马鞍山科教生活","安庆新闻综合","安庆经济生活","潜山综合频道",
        "黄山区融媒","歙县综合频道","休宁新闻综合","黟县新闻综合","宣城综合频道","宣城文旅生活","广德新闻综合","广德生活频道","郎溪新闻频道","宁国新闻综合","铜陵新闻综合","铜陵教育科技",
        "枞阳电视台","霍山综合频道","金寨综合频道","濉溪新闻频道","宿州新闻综合","宿州公共频道","宿州科教频道","萧县新闻综合","五河新闻综合","固镇新闻综合","界首综合频道","利辛新闻综合",
        "涡阳新闻综合","临泉一台", "", "", "", "", "", "", "","", "", "", "", "", "", "", "", "", "", "",   
    ],
    "北京频道": [
    "北京新闻频道","北京影视频道","北京文艺频道","北京生活频道","北京国际频道","北京纪实科教","北京财经频道","北京体育休闲","北京卡酷少儿","北京卫视4K超高清","北京卫视4K超高清","北京IPTV淘BABY",
    "北京IPTV淘剧场","北京IPTV淘电影","北京IPTV淘娱乐","北京IPTV萌宠TV","北京IPTV4K超清","房山电视台","朝阳融媒","密云电视台",
    ],

    "上海频道": [
        "新闻综合", "都市频道", "东方影视", "纪实人文", "第一财经", "五星体育", "东方财经", "ICS频道", "上海教育台", "七彩戏剧", "法治天地", "金色学堂",
        "动漫秀场", "欢笑剧场4K", "生活时尚", "", "", "", "", "",
        "", "", "", "", "", "", "", "", "", "", "",
    ],
    "湖南频道": [
        "湖南国际", "湖南电影", "湖南电视剧", "湖南经视", "湖南娱乐", "湖南公共", "湖南都市", "湖南教育", "芒果互娱", "长沙新闻", "长沙政法", "长沙影视", "长沙女性", "",
        "益阳公共", "抗战剧场", "古装剧场", "高清院线", "先锋兵羽", "", "", "",
        "", "", "", "", "", "", "", "", "", "", "",
    ],
    "湖北频道": [
        "湖北综合", "湖北影视", "湖北生活", "湖北教育", "湖北经视", "荆州新闻", "荆州垄上", "", "", "", "", "", "", "", "", "",
    ],
    "山东频道": [
        "山东综艺", "烟台新闻", "", "", "", "", "", "", "",
    ],
    "广东频道": [
        "", "", "", "", "", "", "广东科教", "广东体育", "广州", "广东珠江", "嘉佳卡通", "茂名综合", "", "", "", "", "",
    ],
    "广西频道": [
        "广西影视", "广西综艺", "广西都市", "广西新闻", "广西移动", "广西科技", "精彩影视", "平南台", "南宁影视", "玉林新闻综合", "", "", "", "", "", "", "",
    ],
    "四川频道": [
        "", "", "", "", "", "", "", "", "蓬安电视台", "", "", "", "", "", "", "", "",
    ],
    "新疆频道": [
        "新疆2", "新疆3", "新疆4", "新疆5", "新疆6", "新疆7", "新疆8", "新疆9", "", "", "", "", "", "", "", "", "",
    ],
}

# 特殊符号映射，在匹配时将特殊符号替换为空
SPECIAL_SYMBOLS = ["HD", "LT", "XF", "", "", "", "", "", "", "", ""]

def clean_channel_name(channel_name):
    """清理频道名称，移除特殊符号和空格"""
    if not channel_name:
        return ""
    
    # 移除特殊符号
    cleaned_name = channel_name
    for symbol in SPECIAL_SYMBOLS:
        if symbol:
            cleaned_name = cleaned_name.replace(symbol, "")
    
    # 移除空格和特殊字符
    cleaned_name = cleaned_name.strip()
    cleaned_name = re.sub(r'\s+', '', cleaned_name)  # 移除所有空白字符
    cleaned_name = re.sub(r'[【】\[\]()（）]', '', cleaned_name)  # 移除括号
    
    return cleaned_name

def get_channel_category(channel_name):
    """根据频道名称获取对应的分类"""
    cleaned_name = clean_channel_name(channel_name)
    
    # 遍历所有分类，查找匹配的频道
    for category, channels in CHANNEL_CATEGORIES.items():
        for template_channel in channels:
            if template_channel and template_channel.strip():
                # 清理模板中的频道名称
                cleaned_template = clean_channel_name(template_channel)
                if cleaned_template and cleaned_template in cleaned_name:
                    return category
    
    # 如果没有找到匹配的分类，返回"其它频道"
    return "其它频道"

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

def find_matching_channel(channel_name, category_template):
    """查找与模板匹配的频道"""
    cleaned_name = clean_channel_name(channel_name)
    
    # 首先尝试精确匹配
    for template_channel in category_template:
        if template_channel and template_channel.strip():
            cleaned_template = clean_channel_name(template_channel)
            if cleaned_name == cleaned_template:
                return template_channel
    
    # 然后尝试前缀匹配（对于CCTV频道特别重要）
    for template_channel in category_template:
        if template_channel and template_channel.strip():
            cleaned_template = clean_channel_name(template_channel)
            # 对于CCTV频道，检查是否以模板频道开头
            if cleaned_template.startswith("CCTV") and cleaned_name.startswith(cleaned_template):
                return template_channel
            # 对于其他频道，检查是否包含模板频道
            elif cleaned_template and cleaned_template in cleaned_name:
                return template_channel
    
    return None

def merge_all_files():
    """合并所有城市的TXT和M3U文件，按照模板分类排序"""
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
    
    # 按照模板重新组织频道
    # 结构: {category: {template_channel: [(original_channel_name, url, city), ...]}}
    organized_channels = {}
    
    # 初始化所有分类
    for category in CHANNEL_CATEGORIES.keys():
        organized_channels[category] = {}
        # 初始化每个分类的模板频道
        for template_channel in CHANNEL_CATEGORIES[category]:
            if template_channel and template_channel.strip():
                organized_channels[category][template_channel] = []
    
    # 添加"其它频道"分类
    organized_channels["其它频道"] = {}
    
    # 用于记录未匹配的频道
    unmatched_channels_by_category = {}
    
    # 将频道分配到模板分类中
    for original_category, channels in all_channels_by_category.items():
        for channel_name, sources in channels.items():
            # 查找匹配的分类和模板频道
            matched = False
            
            for category in CHANNEL_CATEGORIES.keys():
                # 查找匹配的模板频道
                template_channel = find_matching_channel(channel_name, CHANNEL_CATEGORIES[category])
                
                if template_channel:
                    if channel_name not in organized_channels[category]:
                        organized_channels[category][channel_name] = []
                    
                    # 添加所有源
                    for url, city in sources:
                        organized_channels[category][channel_name].append((url, city))
                    matched = True
                    break
            
            # 如果没有找到匹配的分类，放到"其它频道"
            if not matched:
                if channel_name not in organized_channels["其它频道"]:
                    organized_channels["其它频道"][channel_name] = []
                
                # 添加所有源
                for url, city in sources:
                    organized_channels["其它频道"][channel_name].append((url, city))
    
    # 写入合并的TXT文件
    with open("zubo_all.txt", "w", encoding="utf-8") as f:
        f.write(f"{current_time}更新,#genre#\n")
        f.write(f"浙江卫视,http://ali-m-l.cztv.com/channels/lantian/channel001/1080p.m3u8\n")
        
        # 按照模板定义的分类顺序写入
        for category in CHANNEL_CATEGORIES.keys():
            if category in organized_channels and organized_channels[category]:
                f.write(f"{category},#genre#\n")
                
                # 对于央视频道，按照模板顺序写入
                if category == "央视频道":
                    # 按照模板中的顺序写入
                    for template_channel in CHANNEL_CATEGORIES[category]:
                        if template_channel and template_channel.strip():
                            # 查找匹配的实际频道
                            matched_channels = []
                            for channel_name in organized_channels[category].keys():
                                if find_matching_channel(channel_name, [template_channel]):
                                    matched_channels.append(channel_name)
                            
                            # 写入所有匹配的频道
                            for channel_name in matched_channels:
                                for url, city in organized_channels[category][channel_name]:
                                    f.write(f"{channel_name},{url}${city}\n")
                
                # 对于其他分类，按照模板顺序写入
                else:
                    # 按照模板中的顺序写入
                    for template_channel in CHANNEL_CATEGORIES[category]:
                        if template_channel and template_channel.strip():
                            # 查找匹配的实际频道
                            matched_channels = []
                            for channel_name in organized_channels[category].keys():
                                if find_matching_channel(channel_name, [template_channel]):
                                    matched_channels.append(channel_name)
                            
                            # 写入所有匹配的频道
                            for channel_name in matched_channels:
                                for url, city in organized_channels[category][channel_name]:
                                    f.write(f"{channel_name},{url}${city}\n")
                    
                    # 写入未匹配的频道（按字母顺序）
                    remaining_channels = []
                    for channel_name in organized_channels[category].keys():
                        matched = False
                        for template_channel in CHANNEL_CATEGORIES[category]:
                            if template_channel and template_channel.strip():
                                if find_matching_channel(channel_name, [template_channel]):
                                    matched = True
                                    break
                        
                        if not matched:
                            remaining_channels.append(channel_name)
                    
                    for channel_name in sorted(remaining_channels):
                        for url, city in organized_channels[category][channel_name]:
                            f.write(f"{channel_name},{url}${city}\n")
    
    # 处理"其它频道"分类
    if organized_channels.get("其它频道") and organized_channels["其它频道"]:
        with open("zubo_all.txt", "a", encoding="utf-8") as f:
            f.write(f"其它频道,#genre#\n")
            
            # 获取所有其它频道并按字母顺序排序
            other_channels = sorted(organized_channels["其它频道"].keys())
            for channel_name in other_channels:
                for url, city in organized_channels["其它频道"][channel_name]:
                    f.write(f"{channel_name},{url}${city}\n")
    
    total_sources = sum(len(sources) for category in organized_channels.values() for sources in category.values())
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
        for category in CHANNEL_CATEGORIES.keys():
            if category in organized_channels and organized_channels[category]:
                # 对于央视频道，按照模板顺序写入
                if category == "央视频道":
                    # 按照模板中的顺序写入
                    for template_channel in CHANNEL_CATEGORIES[category]:
                        if template_channel and template_channel.strip():
                            # 查找匹配的实际频道
                            matched_channels = []
                            for channel_name in organized_channels[category].keys():
                                if find_matching_channel(channel_name, [template_channel]):
                                    matched_channels.append(channel_name)
                            
                            # 写入所有匹配的频道
                            for channel_name in matched_channels:
                                # 查找台标
                                logo_url = logo_dict.get(channel_name, "")
                                
                                # 写入该频道的所有源
                                for url, city in organized_channels[category][channel_name]:
                                    display_name = f"{channel_name}${city}"
                                    
                                    if logo_url:
                                        f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" tvg-logo="{logo_url}" group-title="{category}",{display_name}\n')
                                    else:
                                        f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" group-title="{category}",{display_name}\n')
                                    f.write(f"{url}\n")
                
                # 对于其他分类，按照模板顺序写入
                else:
                    # 按照模板中的顺序写入
                    for template_channel in CHANNEL_CATEGORIES[category]:
                        if template_channel and template_channel.strip():
                            # 查找匹配的实际频道
                            matched_channels = []
                            for channel_name in organized_channels[category].keys():
                                if find_matching_channel(channel_name, [template_channel]):
                                    matched_channels.append(channel_name)
                            
                            # 写入所有匹配的频道
                            for channel_name in matched_channels:
                                # 查找台标
                                logo_url = logo_dict.get(channel_name, "")
                                
                                # 写入该频道的所有源
                                for url, city in organized_channels[category][channel_name]:
                                    display_name = f"{channel_name}${city}"
                                    
                                    if logo_url:
                                        f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" tvg-logo="{logo_url}" group-title="{category}",{display_name}\n')
                                    else:
                                        f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" group-title="{category}",{display_name}\n')
                                    f.write(f"{url}\n")
                    
                    # 写入未匹配的频道（按字母顺序）
                    remaining_channels = []
                    for channel_name in organized_channels[category].keys():
                        matched = False
                        for template_channel in CHANNEL_CATEGORIES[category]:
                            if template_channel and template_channel.strip():
                                if find_matching_channel(channel_name, [template_channel]):
                                    matched = True
                                    break
                        
                        if not matched:
                            remaining_channels.append(channel_name)
                    
                    for channel_name in sorted(remaining_channels):
                        # 查找台标
                        logo_url = logo_dict.get(channel_name, "")
                        
                        # 写入该频道的所有源
                        for url, city in organized_channels[category][channel_name]:
                            display_name = f"{channel_name}${city}"
                            
                            if logo_url:
                                f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" tvg-logo="{logo_url}" group-title="{category}",{display_name}\n')
                            else:
                                f.write(f'#EXTINF:-1 tvg-id="" tvg-name="{channel_name}" group-title="{category}",{display_name}\n')
                            f.write(f"{url}\n")
        
        # 处理"其它频道"分类
        if organized_channels.get("其它频道") and organized_channels["其它频道"]:
            other_channels = sorted(organized_channels["其它频道"].keys())
            for channel_name in other_channels:
                # 查找台标
                logo_url = logo_dict.get(channel_name, "")
                
                # 写入该频道的所有源
                for url, city in organized_channels["其它频道"][channel_name]:
                    display_name = f"{channel_name}${city}"
                    
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
        for category in CHANNEL_CATEGORIES.keys():
            if category in organized_channels and organized_channels[category]:
                f.write(f"{category},#genre#\n")
                
                # 对于央视频道，按照模板顺序写入
                if category == "央视频道":
                    # 按照模板中的顺序写入
                    for template_channel in CHANNEL_CATEGORIES[category]:
                        if template_channel and template_channel.strip():
                            # 查找匹配的实际频道
                            matched_channels = []
                            for channel_name in organized_channels[category].keys():
                                if find_matching_channel(channel_name, [template_channel]):
                                    matched_channels.append(channel_name)
                            
                            # 只取每个频道的第一个源
                            for channel_name in matched_channels:
                                if organized_channels[category][channel_name]:
                                    url, city = organized_channels[category][channel_name][0]
                                    f.write(f"{channel_name},{url}\n")
                
                # 对于其他分类，按照模板顺序写入
                else:
                    # 按照模板中的顺序写入
                    for template_channel in CHANNEL_CATEGORIES[category]:
                        if template_channel and template_channel.strip():
                            # 查找匹配的实际频道
                            matched_channels = []
                            for channel_name in organized_channels[category].keys():
                                if find_matching_channel(channel_name, [template_channel]):
                                    matched_channels.append(channel_name)
                            
                            # 只取每个频道的第一个源
                            for channel_name in matched_channels:
                                if organized_channels[category][channel_name]:
                                    url, city = organized_channels[category][channel_name][0]
                                    f.write(f"{channel_name},{url}\n")
                    
                    # 写入未匹配的频道（按字母顺序）
                    remaining_channels = []
                    for channel_name in organized_channels[category].keys():
                        matched = False
                        for template_channel in CHANNEL_CATEGORIES[category]:
                            if template_channel and template_channel.strip():
                                if find_matching_channel(channel_name, [template_channel]):
                                    matched = True
                                    break
                        
                        if not matched:
                            remaining_channels.append(channel_name)
                    
                    for channel_name in sorted(remaining_channels):
                        if organized_channels[category][channel_name]:
                            url, city = organized_channels[category][channel_name][0]
                            f.write(f"{channel_name},{url}\n")
        
        # 处理"其它频道"分类
        if organized_channels.get("其它频道") and organized_channels["其它频道"]:
            f.write(f"其它频道,#genre#\n")
            other_channels = sorted(organized_channels["其它频道"].keys())
            for channel_name in other_channels:
                if organized_channels["其它频道"][channel_name]:
                    url, city = organized_channels["其它频道"][channel_name][0]
                    f.write(f"{channel_name},{url}\n")
    
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
                f.write("CCTV1,166:7200\n")
                f.write("CCTV2,235:7752\n")
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
