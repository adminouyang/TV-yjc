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
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

IP_DIR = "Hotel/ip"
# 创建IP目录
if not os.path.exists(IP_DIR):
    os.makedirs(IP_DIR)

# 频道分类定义
CHANNEL_CATEGORIES = {
    "央视频道": [
        "CCTV1", "CCTV2", "CCTV3", "CCTV4", "CCTV4欧洲", "CCTV4美洲", "CCTV5", "CCTV5+", "CCTV6", "CCTV7",
        "CCTV8", "CCTV9", "CCTV10", "CCTV11", "CCTV12", "CCTV13", "CCTV14", "CCTV15", "CCTV16", "CCTV17",
        "兵器科技", "风云音乐", "风云足球", "风云剧场", "怀旧剧场", "第一剧场", "女性时尚", "世界地理", "央视台球", "高尔夫网球",
        "央视文化精品", "卫生健康", "电视指南", "老故事", "中学生", "发现之旅", "书法频道", "国学频道", "环球奇观",
        "CETV1", "CETV2", "CETV3", "CETV4", "早期教育","CGTN纪录",
    ],
    "卫视频道": [
        "重温经典","湖南卫视", "浙江卫视", "江苏卫视", "东方卫视", "深圳卫视", "北京卫视", "广东卫视", "广西卫视", "东南卫视", "海南卫视",
        "河北卫视", "河南卫视", "湖北卫视", "江西卫视", "四川卫视", "重庆卫视", "贵州卫视", "云南卫视", "天津卫视", "安徽卫视", "厦门卫视",
        "山东卫视", "辽宁卫视", "黑龙江卫视", "吉林卫视", "内蒙古卫视", "宁夏卫视", "山西卫视", "陕西卫视", "甘肃卫视", "青海卫视",
        "新疆卫视", "西藏卫视", "三沙卫视", "兵团卫视", "延边卫视", "安多卫视", "康巴卫视", "农林卫视", "山东教育卫视",
    ],
    "数字频道": [
        "CHC动作电影", "CHC家庭影院", "CHC影迷电影", "淘电影", "淘精彩", "淘剧场", "淘4K", "淘娱乐", "淘BABY", "淘萌宠", 
         "海看大片", "经典电影", "精彩影视", "喜剧影院", "动作影院", "精品剧场","IPTV戏曲", "求索纪录", "求索科学", "法制天地",
        "求索生活", "求索动物", "纪实人文", "金鹰纪实", "纪实科教", "睛彩青少", "睛彩竞技", "睛彩篮球", "睛彩广场舞", "魅力足球", "五星体育", "体育赛事",
        "劲爆体育", "快乐垂钓", "四海钓鱼", "茶频道", "先锋乒羽", "天元围棋", "汽摩", "车迷频道", "梨园频道", "文物宝库", "武术世界",
        "乐游", "生活时尚", "都市剧场", "欢笑剧场", "金色学堂", "动漫秀场", "新动漫", "金鹰卡通", "优漫卡通", "哈哈炫动", "嘉佳卡通", 
        "优优宝贝", "中国交通", "中国天气",  "网络棋牌", 
    ],
    "港澳台频道": [
        "凤凰卫视中文台", "凤凰卫视资讯台", "凤凰卫视香港台", "凤凰卫视电影台", "龙祥时代","星空卫视", "CHANNEL[V]",  "","", "", "", "", "", "", "",
    ],
    "安徽频道": [
        "安徽影视", "安徽经济生活", "安徽公共", "安徽综艺体育", "安徽农业科教", "阜阳公共频道", "马鞍山新闻综合", "马鞍山公共", "", "", "", "环球奇观",
        "临泉一台", "", "", "", "", "", "", "",
        "", "", "", "", "", "", "", "", "", "", "",
    ],
    "北京频道": [
         "北京纪实科教", "","", "", "", "", "", "", "","北京卡酷少儿", 
    ],
    "上海频道": [
        "新闻综合", "都市频道", "东方影视", "纪实人文", "第一财经", "五星体育", "东方财经", "ICS频道", "上海教育台", "七彩戏剧", "法治天地", "金色学堂",
        "动漫秀场", "欢笑剧场4K", "生活时尚", "", "", "", "", "",
        "", "", "", "", "", "", "", "", "", "", "",
    ],
    "湖南频道": [
        "湖南国际", "湖南电影", "湖南电视剧", "湖南经视", "湖南娱乐", "湖南公共", "湖南都市","湖南教育", "芒果互娱", "长沙新闻", "长沙政法", "长沙影视", "长沙女性", "",
        "益阳公共", "抗战剧场", "古装剧场", "高清院线", "先锋兵羽", "望城综合", "花鼓戏", "",
        "", "", "", "", "", "", "", "", "", "", "",
    ],
    "湖北频道": [
        "湖北综合", "湖北影视", "湖北生活", "湖北教育", "湖北经视", "荆州新闻", "荆州垄上", "", "","", "", "", "", "", "", "",
    ],
    "河北频道": [
         "河北影视剧", "河北都市","河北经济", "河北公共", "河北少儿科教","河北三农", "衡水新闻", "衡水公共", "", "", "", "", "", "",
    ],
    "山东频道": [
         "山东综艺","山东影视", "山东齐鲁", "山东农科","山东体育","山东生活", "山东少儿","烟台新闻","山东教育", "临沂导视", "临沂图文", "临沂综合", "临沂农科", "兰陵导视", "兰陵公共", "兰陵综合",
    ],
    "广东频道": [
        "广东影视", "", "", "", "", "", "广东科教", "广东体育", "广州新闻", "广东珠江", "深圳都市", "深圳少儿", "嘉佳卡通", "茂名综合", "", "", "",
    ],
    "广西频道": [
        "广西影视", "广西综艺", "广西都市", "广西新闻", "广西移动", "广西科技", "精彩影视", "平南台", "南宁影视", "玉林新闻综合","", "", "", "", "", "", "",
    ],
    "四川频道": [
        "四川新闻", "四川文化旅游", "四川影视文艺", "峨眉电影", "熊猫影院", "广元综合", "广元公共", "四川卫视-乡村公共", "蓬安电视台", "","", "", "", "", "", "", "金熊猫卡通",
    ],
    "陕西频道": [
        "", "", "", "", "", "", "", "", "三门峡新闻综合", "灵宝新闻综合","", "", "", "", "", "", "",
    ],    
    "浙江频道": [
        "浙江新闻", "杭州影视", "", "", "", "", "", "", "", "","", "", "", "", "", "", "",
    ], 
    "吉林频道": [
        "吉林影视", "吉林都市", "吉林乡村", "吉林教育", "吉林综艺", "吉林生活", "", "", "长影频道", "松原公共","松原", "", "", "", "", "", "",
    ],
    "新疆频道": [
        "新疆2", "新疆3", "新疆4", "新疆5", "新疆6", "新疆7", "新疆8", "新疆9", "", "","", "", "", "", "", "", "",
    ],
}

# 特殊符号映射，在匹配时将特殊符号替换为空
SPECIAL_SYMBOLS = ["HD", "LT", "XF", "-", "_", " ", ".", "·", "高清", "标清", "超清", "H265", "4K", "FHD", "HDTV"]

# 移除特殊符号的函数
def remove_special_symbols(text):
    """移除频道名称中的特殊符号"""
    for symbol in SPECIAL_SYMBOLS:
        text = text.replace(symbol, "")
    
    # 移除多余的空格
    text = re.sub(r'\s+', '', text)
    return text.strip()

# 改进的频道名称映射，使用精确匹配
CHANNEL_MAPPING = {
    "CCTV1": ["CCTV1", "CCTV-1", "CCTV1综合", "CCTV1高清", "CCTV1HD", "cctv1","中央1台","sCCTV1-综合","CCTV01"],
    "CCTV2": ["CCTV2", "CCTV-2", "CCTV2财经", "CCTV2高清", "CCTV2HD", "cctv2","中央2台","aCCTV2","sCCTV2-财经","CCTV02"],
    "CCTV3": ["CCTV3", "CCTV-3", "CCTV3综艺", "CCTV3高清", "CCTV3HD", "cctv3","中央3台","acctv3","sCCTV3-综艺","CCTV03"],
    "CCTV4": ["CCTV4", "CCTV-4", "CCTV4中文国际", "CCTV4高清", "CCTV4HD", "cctv4","中央4台","aCCTV4","sCCTV4-国际","CCTV04"],
    "CCTV5": ["CCTV5", "CCTV-5", "CCTV5体育", "CCTV5高清", "CCTV5HD", "cctv5","中央5台","sCCTV5-体育","CCTV05"],
    "CCTV5+": ["CCTV5+", "CCTV-5+", "CCTV5+体育赛事", "CCTV5+高清", "CCTV5+HD", "cctv5+", "CCTV5plus"],
    "CCTV6": ["CCTV6", "CCTV-6", "CCTV6电影", "CCTV6高清", "CCTV6HD", "cctv6","中央6台","sCCTV6-电影","CCTV06"],
    "CCTV7": ["CCTV7", "CCTV-7", "CCTV7军事", "CCTV7高清", "CCTV7HD", "cctv7","中央7台","CCTV07"],
    "CCTV8": ["CCTV8", "CCTV-8", "CCTV8电视剧", "CCTV8高清", "CCTV8HD", "cctv8","中央8台","sCCTV8-电视剧","CCTV08"],
    "CCTV9": ["CCTV9", "CCTV-9", "CCTV9纪录", "CCTV9高清", "CCTV9HD", "cctv9","中央9台","sCCTV9-纪录","CCTV09"],
    "CCTV10": ["CCTV10", "CCTV-10", "CCTV10科教", "CCTV10高清", "CCTV10HD", "cctv10","中央10台","sCCTV10-科教"],
    "CCTV11": ["CCTV11", "CCTV-11", "CCTV11戏曲", "CCTV11高清", "CCTV11HD", "cctv11", "中央11台","sCCTV11-戏曲"],
    "CCTV12": ["CCTV12", "CCTV-12", "CCTV12社会与法", "CCTV12高清", "CCTV12HD", "cctv12","中央12台","sCCTV12-社会与法"],
    "CCTV13": ["CCTV13", "CCTV-13", "CCTV13新闻", "CCTV13高清", "CCTV13HD", "cctv13","中央13台","sCCTV13-新闻"],
    "CCTV14": ["CCTV14", "CCTV-14", "CCTV14少儿", "CCTV14高清", "CCTV14HD", "cctv14","中央14台","sCCTV14-少儿"],
    "CCTV15": ["CCTV15", "CCTV-15", "CCTV15音乐", "CCTV15高清", "CCTV15HD", "cctv15","中央15台","sCCTV15-音乐"],
    "CCTV16": ["CCTV16", "CCTV-16", "CCTV16奥林匹克", "CCTV16高清", "CCTV16HD", "cctv16","中央16台"],
    "CCTV17": ["CCTV17", "CCTV-17", "CCTV17农业农村", "CCTV17高清", "CCTV17HD", "cctv17","中央17台"],
    
    "CCTV4欧洲": ["CCTV4欧洲", "CCTV-4欧洲", "CCTV4欧洲高清", "CCTV4欧洲HD"],
    "CCTV4美洲": ["CCTV4美洲", "CCTV-4美洲", "CCTV4美洲高清", "CCTV4美洲HD"],
    
    "兵器科技": ["兵器科技", "CCTV兵器科技", "兵器科技频道"],
    "风云音乐": ["风云音乐", "CCTV风云音乐"],
    "第一剧场": ["第一剧场", "CCTV第一剧场"],
    "风云足球": ["风云足球", "CCTV风云足球"],
    "风云剧场": ["风云剧场", "CCTV风云剧场"],
    "怀旧剧场": ["怀旧剧场", "CCTV怀旧剧场"],
    "女性时尚": ["女性时尚", "CCTV女性时尚"],
    "世界地理": ["地理世界", "CCTV世界地理"],
    "央视台球": ["央视台球", "CCTV央视台球"],
    "高尔夫网球": ["高尔夫网球", "央视高网", "CCTV高尔夫网球", "高尔夫"],
    "央视文化精品": ["央视文化精品", "CCTV央视文化精品"],
    "卫生健康": ["卫生健康", "CCTV卫生健康"],
    "电视指南": ["电视指南", "CCTV电视指南"],
    "中国天气": ["中国气象"],
    "安多卫视": ["1020"],
    "安徽卫视": ["安徽卫视高清"],
    "北京卫视": ["北京卫视HD","北京卫视高清"],
    "东南卫视": ["福建东南", "东南卫视"],
    "东方卫视": ["上海卫视", "东方卫视","SBN"],
    "农林卫视": ["陕西农林卫视", "农林卫视"],
    "江苏卫视": ["江苏卫视HD","江苏卫视高清"],
    "江西卫视": ["江西卫视"],
    "黑龙江卫视": ["黑龙江卫视"],
    "吉林卫视": ["吉林卫视"],
    "辽宁卫视": ["辽宁卫视HD"],
    "甘肃卫视": ["甘肃卫视"],
    "湖南卫视": ["湖南卫视", "湖南电视"],
    "河南卫视": ["河南卫视"],
    "河北卫视": ["河北卫视"],
    "湖北卫视": ["湖北卫视"],
    "海南卫视": ["旅游卫视", "海南卫视HD"],
    "重庆卫视": ["重庆卫视"],
    "深圳卫视": ["深圳卫视高清", "深圳"],
    "广东卫视": ["广东卫视高清"],
    "广西卫视": ["广西卫视"],
    "天津卫视": ["天津卫视"],
    "山东卫视": ["山东高清","山东卫视高清","山东卫视HD"],
    "星空卫视": ["星空卫视", "星空衛視", "XF星空卫视"],
    "四川卫视": ["四川卫视","四川卫视高清"],
    "浙江卫视": ["浙江卫视高清"],
    "贵州卫视": ["贵州卫视"],
    "南方卫视": ["南方卫视"],
    "内蒙古卫视": ["内蒙古卫视", "内蒙古", "内蒙卫视"],
    "康巴卫视": ["康巴卫视"],
    "山东教育卫视": ["山东教育", "山东教育卫视"],
    "新疆卫视": ["新疆卫视", "新疆1"],
    "西藏卫视": ["西藏卫视", "XZTV2"],
    
    "CETV1": ["中国教育1台", "中国教育一台", "中国教育一套高清", "教育一套" ,"CETV-1高清","中国教育"],
    "CETV2": ["中国教育2台", "中国教育二台", "中国教育二套高清"],
    "CETV3": ["中国教育3台", "中国教育三台", "中国教育三套高清"],
    "CETV4": ["中国教育4台", "中国教育四台", "中国教育四套高清"],
    
    "CHC动作电影": ["动作电影"],
    "CHC家庭影院": ["家庭影院"],
    "CHC影迷电影": ["高清电影"],
    
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
    "上海纪实": ["上海纪实高清"],
    "星空卫视": ["星空卫视", "星空衛視"],
    "CHANNEL[V]": ["Channel[V]", "CHANNEL[V]"],
    "凤凰卫视中文台": ["凤凰卫视中文台", "凤凰中文", "凤凰卫视"],
    "凤凰卫视香港台": ["凤凰卫视香港台", "凤凰香港"],
    "凤凰卫视资讯台": ["凤凰卫视资讯台", "凤凰资讯", "凤凰咨询"],
    "凤凰卫视电影台": ["凤凰卫视电影台", "凤凰电影", "鳳凰衛視電影台"],
    "北京纪实科教": ["BTV高清","纪实科教"],
    "北京卡酷少儿": ["卡酷","卡酷少儿"],
    "河北影视剧": ["河北影视"],
    "河北三农": ["河北农民"],
    "河北少儿科教": ["少儿科教"],
    "湖南电影": ["湖南电影高清", "湖南电影HD"],
    "湖南娱乐": ["湖南娱乐高清", "湖南娱乐HD"],
    "湖南都市": ["湖南都市高清", "湖南都市HD"],
    "湖南国际": ["湖南国际高清", "湖南国际HD"],
    "湖南公共": ["湖南公共HD"],
    "长沙政法": ["长沙政法HD"],
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
    "广东影视": ["广东影视-1"],
    "广东科教": ["广东科教", "广东科教高清电信"],
    "广东体育": ["广东体育高清", "DTV1"],
    "广州新闻": ["广州", "XF广州台"],
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
    "都市剧场": ["都市剧场", "SiTV都市剧场", "上海都市剧场", "都市时尚"],
    "游戏风云": ["游戏风云", "SiTV游戏风云", "上海游戏风云"],
    "金色学堂": ["金色学堂", "SiTV金色学堂", "上海金色学堂"],
    "动漫秀场": ["动漫秀场", "SiTV动漫秀场", "上海动漫秀场"],
    "卡酷少儿": ["卡酷少儿", "卡酷动画", "卡酷动漫", "北京卡酷","北京少儿"],
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
        return []
    
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
    
    # 修复：总是更新IP文件，即使可用IP列表为空
    with open(province_file, 'w', encoding='utf-8') as f:
        for ip_port in available_ips:
            f.write(f"{ip_port}\n")
    
    if available_ips:
        print(f"\n✓ 已更新 {province_file}")
        print(f"  原始IP数量: {total_ips}")
        print(f"  可用IP数量: {len(available_ips)}")
        print(f"  不可用IP已删除: {total_ips - len(available_ips)}")
    else:
        print(f"\n✓ 已更新 {province_file}，没有可用的IP，文件已清空")
    
    return available_ips

# 读取文件并设置参数
def read_config(config_file):
    ip_configs = []
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                # 分割IP:端口和地区
                if '$' in line:
                    # 格式: IP:端口$地区
                    ip_port, region = line.split('$', 1)
                else:
                    # 格式: IP:端口 (无地区)
                    ip_port = line
                    region = ""
                
                # 分割IP和端口
                if ':' in ip_port:
                    ip_part, port = ip_port.split(':', 1)
                    
                    # 解析IP的四个部分
                    parts = ip_part.split('.')
                    if len(parts) == 4:
                        a, b, c, d = parts
                        
                        # 注意：原代码会将IP的第四段改为1
                        # 例如 182.122.225.78 会变成 182.122.225.1
                        # 如果你不需要这个修改，可以去掉这行
                        ip = f"{a}.{b}.{c}.1"
                        
                        # 如果你需要原IP，可以这样：
                        # ip = ip_part
                        
                        ip_configs.append((ip, port))   #, region
                    else:
                        print(f"跳过无效IP格式: {ip_part}")
                
        return ip_configs
    except Exception as e:
        print(f"读取文件错误: {e}")
        return []
        
# 发送get请求检测url是否可访问
def check_ip_port(ip_port, url_end):
    try:
        url = f"http://{ip_port}{url_end}"
        resp = requests.get(url, timeout=3)
        resp.raise_for_status()
        if "tsfile" in resp.text or "hls" in resp.text or "m3u8" in resp.text:
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
        # 分割URL，获取协议和域名部分
        urls = url.split('/', 3)
        url_x = f"{urls[0]}//{urls[2]}"
        
        if "iptv" in url:
            response = requests.get(url, timeout=3)
            json_data = response.json()
            for item in json_data.get('data', []):
                if isinstance(item, dict):
                    name = item.get('name')
                    urlx = item.get('url')
                    if urlx and ("tsfile" in urlx or "m3u8" in urlx):
                        # 确保urlx以斜杠开头，避免双斜杠
                        if not urlx.startswith('/'):
                            urlx = '/' + urlx
                        urld = f"{url_x}{urlx}"
                        hotel_channels.append((name, urld))
        elif "ZHGXTV" in url:
            response = requests.get(url, timeout=2)
            json_data = response.content.decode('utf-8')
            data_lines = json_data.split('\n')
            for line in data_lines:
                if "," in line and ("hls" in line or "m3u8" in line):
                    name, channel_url = line.strip().split(',')
                    parts = channel_url.split('/', 3)
                    if len(parts) >= 4:
                        urld = f"{url_x}/{parts[3]}"
                        hotel_channels.append((name, urld))
        return hotel_channels
    except Exception as e:
        print(f"解析频道错误 {url}: {e}")
        return []

# 测速函数，对速度过慢的进行重新测速
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
                
                # 记录最佳速度
                best_speed = 0.0
                attempts = 0
                max_attempts = 2  # 最多尝试2次
                
                while attempts < max_attempts:
                    attempts += 1
                    try:
                        # 获取m3u8文件内容
                        response = requests.get(channel_url, timeout=2)
                        if response.status_code != 200:
                            if attempts < max_attempts:
                                print(f"第{attempts}次测速 {channel_name}: HTTP {response.status_code}，将重试")
                            continue
                            
                        lines = response.text.strip().split('\n')
                        ts_lists = [line.split('/')[-1] for line in lines if line.startswith('#') == False]
                        if not ts_lists:
                            if attempts < max_attempts:
                                print(f"第{attempts}次测速 {channel_name}: 没有找到TS列表，将重试")
                            continue
                        
                        # 获取TS文件的URL
                        channel_url_t = channel_url.rstrip(channel_url.split('/')[-1])
                        ts_url = channel_url_t + ts_lists[0]
                        
                        # 测速逻辑
                        start_time = time.time()
                        try:
                            with eventlet.Timeout(5, False):
                                ts_response = requests.get(ts_url, timeout=6, stream=True)
                                if ts_response.status_code != 200:
                                    if attempts < max_attempts:
                                        print(f"第{attempts}次测速 {channel_name}: TS文件HTTP {ts_response.status_code}，将重试")
                                    continue
                                
                                # 读取部分内容进行测速
                                content_length = 0
                                chunk_size = 1024 * 1024  # 1MB
                                for chunk in ts_response.iter_content(chunk_size=chunk_size):
                                    if chunk:
                                        content_length += len(chunk)
                                        # 只读取1MB用于测速
                                        if content_length >= chunk_size:
                                            break
                                
                                resp_time = (time.time() - start_time) * 1
                                
                                if content_length > 0 and resp_time > 0:
                                    normalized_speed = content_length / resp_time / 1024 / 1024
                                    
                                    # 更新最佳速度
                                    if normalized_speed > best_speed:
                                        best_speed = normalized_speed
                                    
                                    # 如果速度合格，不再重试
                                    if normalized_speed > 0.001 and attempts < max_attempts:
                                        break
                                    else:
                                        if attempts < max_attempts:
                                            print(f"第{attempts}次测速 {channel_name}: {normalized_speed:.3f} MB/s，将重试")
                                else:
                                    if attempts < max_attempts:
                                        print(f"第{attempts}次测速 {channel_name}: 获取内容失败，将重试")
                        except eventlet.Timeout:
                            if attempts < max_attempts:
                                print(f"第{attempts}次测速 {channel_name}: 请求超时，将重试")
                            continue
                        except Exception as e:
                            if attempts < max_attempts:
                                print(f"第{attempts}次测速 {channel_name} 失败: {str(e)}，将重试")
                            continue
                            
                    except Exception as e:
                        if attempts < max_attempts:
                            print(f"第{attempts}次测速 {channel_name} 处理失败: {str(e)}，将重试")
                        continue
                
                # 根据最佳速度决定是否保留
                if best_speed > 0.001:
                    result = channel_name, channel_url, f"{best_speed:.3f}"
                    if attempts > 1:
                        print(f"✓ {channel_name}, {channel_url}: {best_speed:.3f} MB/s (经过{attempts}次测速)")
                    else:
                        print(f"✓ {channel_name}, {channel_url}: {best_speed:.3f} MB/s")
                    results.append(result)
                else:
                    print(f"× {channel_name}, {channel_url}: 经过{attempts}次测速，最佳速度 {best_speed:.3f} MB/s，已过滤")
                
                checked[0] += 1
            except Exception as e:
                checked[0] += 1
                print(f"处理 {channel_name} 时发生错误: {e}")
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

# 精确频道名称匹配函数
def exact_channel_match(channel_name, pattern_name):
    """
    更严格的精确匹配频道名称
    避免CCTV1匹配到CCTV10、CCTV-10、CCTV-11等问题
    """
    # 清理名称
    clean_name = remove_special_symbols(channel_name.strip().lower())
    clean_pattern = remove_special_symbols(pattern_name.strip().lower())
    
    # 如果清理后完全相等，直接返回True
    if clean_name == clean_pattern:
        return True
    
    # 处理CCTV数字频道
    cctv_match = re.match(r'^cctv[-_\s]?(\d+[a-z]?)$', clean_name)
    pattern_match = re.match(r'^cctv[-_\s]?(\d+[a-z]?)$', clean_pattern)
    
    if cctv_match and pattern_match:
        # 提取数字部分进行比较
        cctv_num1 = cctv_match.group(1)
        cctv_num2 = pattern_match.group(1)
        
        # 如果数字不同，不匹配
        if cctv_num1 != cctv_num2:
            return False
        else:
            # 数字相同，再检查完整名称
            return clean_name == clean_pattern
    
    # 处理CCTV5+等带+的频道
    if "+" in clean_name and "+" in clean_pattern:
        if "cctv5+" in clean_name and "cctv5+" in clean_pattern:
            return True
    
    # 对于非CCTV数字频道，使用更严格的前缀匹配
    # 检查clean_pattern是否是clean_name的前缀，但要有边界检查
    if clean_pattern in clean_name:
        # 确保不是像"CCTV1"匹配"CCTV10"这样的情况
        if clean_pattern.endswith(('1', '2', '3', '4', '5', '6', '7', '8', '9', '0')):
            # 如果是数字结尾，需要确保下一个字符是结束符
            pattern_len = len(clean_pattern)
            if len(clean_name) > pattern_len:
                next_char = clean_name[pattern_len]
                if next_char.isdigit():
                    return False
        return True
    
    return False

# 统一频道名称 - 使用精确匹配
def unify_channel_name(channels_list):
    new_channels_list = []
    
    for name, channel_url, speed in channels_list:
        original_name = name
        unified_name = None
        
        # 清理原始名称
        clean_name = remove_special_symbols(name.strip().lower())
        
        # 首先尝试精确的数字匹配
        cctv_match = re.search(r'^cctv[-_\s]?(\d+[a-z]?)$', clean_name, re.IGNORECASE)
        if cctv_match:
            cctv_num = cctv_match.group(1)
            
            # 构建标准的CCTV名称
            if cctv_num == "5+":
                standard_name = "CCTV5+"
            else:
                standard_name = f"CCTV{cctv_num}"
            
            # 在映射表中查找标准名称
            if standard_name in CHANNEL_MAPPING:
                unified_name = standard_name
                print(f"数字匹配: '{original_name}' -> '{standard_name}'")
        
        # 如果没有通过数字匹配，再尝试映射表匹配
        if not unified_name:
            for standard_name, variants in CHANNEL_MAPPING.items():
                for variant in variants:
                    if exact_channel_match(name, variant):
                        unified_name = standard_name
                        break
                if unified_name:
                    break
        
        # 如果还没有找到，尝试其他匹配策略
        if not unified_name:
            # 处理特殊格式的CCTV频道
            for pattern in [r'cctv[-\s]?(\d+)高清?', r'cctv[-\s]?(\d+)hd', r'cctv[-\s]?(\d+).*']:
                match = re.search(pattern, clean_name, re.IGNORECASE)
                if match:
                    cctv_num = match.group(1)
                    if cctv_num == "5+":
                        standard_name = "CCTV5+"
                    else:
                        standard_name = f"CCTV{cctv_num}"
                    
                    if standard_name in CHANNEL_MAPPING:
                        unified_name = standard_name
                        print(f"正则匹配: '{original_name}' -> '{standard_name}'")
                        break
        
        # 如果还是没有找到，保留原名称
        if not unified_name:
            unified_name = original_name
        
        new_channels_list.append(f"{unified_name},{channel_url},{speed}\n")
        if original_name != unified_name:
            print(f"频道名称统一: '{original_name}' -> '{unified_name}'")
    
    return new_channels_list

# 按照CHANNEL_CATEGORIES中指定的顺序排序
def sort_channels_by_specified_order(channels_list, category_channels):
    """按照指定的顺序对频道进行排序"""
    # 创建频道到索引的映射
    channel_order = {channel: index for index, channel in enumerate(category_channels)}
    
    def get_channel_sort_key(item):
        """获取频道的排序键值"""
        name, url, speed = item
        
        # 如果频道在指定列表中，使用指定顺序
        if name in channel_order:
            return (channel_order[name], -float(speed))  # 相同频道按速度降序
        else:
            # 不在列表中的频道放在最后，按名称排序
            return (float('inf'), name)
    
    # 按照指定顺序排序
    return sorted(channels_list, key=get_channel_sort_key)

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

# 分组并排序频道
def group_and_sort_channels_by_category(categorized_channels):
    """对分类后的频道进行分组、排序和数量限制"""
    processed_categories = {}
    
    for category, channels in categorized_channels.items():
        if not channels:
            continue
            
        if category in CHANNEL_CATEGORIES:
            # 获取该分类的频道列表顺序
            category_order = CHANNEL_CATEGORIES[category]
            
            if category == "央视频道":
                # 央视频道：先按指定顺序分组，然后按速度排序
                channel_groups = {}
                for name, url, speed in channels:
                    if name not in channel_groups:
                        channel_groups[name] = []
                    channel_groups[name].append((name, url, speed))
                
                # 对每个频道按速度排序并限制数量
                grouped_channels = []
                for channel_name in category_order:
                    if channel_name in channel_groups:
                        # 对每个频道的URL按速度排序
                        url_list = channel_groups[channel_name]
                        url_list.sort(key=lambda x: -float(x[2]))
                        # 限制每个频道最多RESULTS_PER_CHANNEL个URL
                        url_list = url_list[:RESULTS_PER_CHANNEL]
                        grouped_channels.extend(url_list)
                        del channel_groups[channel_name]
                
                # 添加不在指定顺序中的其他频道
                for channel_name, url_list in channel_groups.items():
                    url_list.sort(key=lambda x: -float(x[2]))
                    url_list = url_list[:RESULTS_PER_CHANNEL]
                    grouped_channels.extend(url_list)
                
                # 按照指定顺序排序
                grouped_channels = sort_channels_by_specified_order(grouped_channels, category_order)
                processed_categories[category] = grouped_channels
            else:
                # 其他分类：先分组，按速度排序，限制数量，然后按指定顺序排序
                channel_groups = {}
                for name, url, speed in channels:
                    if name not in channel_groups:
                        channel_groups[name] = []
                    channel_groups[name].append((name, url, speed))
                
                # 对每个频道的URL按速度排序
                grouped_channels = []
                for channel_name in category_order:
                    if channel_name in channel_groups:
                        url_list = channel_groups[channel_name]
                        url_list.sort(key=lambda x: -float(x[2]))
                        url_list = url_list[:RESULTS_PER_CHANNEL]
                        grouped_channels.extend(url_list)
                        del channel_groups[channel_name]
                
                # 添加不在指定顺序中的其他频道
                for channel_name, url_list in channel_groups.items():
                    url_list.sort(key=lambda x: -float(x[2]))
                    url_list = url_list[:RESULTS_PER_CHANNEL]
                    grouped_channels.extend(url_list)
                
                # 按照指定顺序排序
                grouped_channels = sort_channels_by_specified_order(grouped_channels, category_order)
                processed_categories[category] = grouped_channels
        else:
            # 其他频道分类：简单按速度排序
            channels.sort(key=lambda x: -float(x[2]))
            channel_groups = {}
            
            for name, url, speed in channels:
                if name not in channel_groups:
                    channel_groups[name] = []
                channel_groups[name].append((name, url, speed))
            
            grouped_channels = []
            for channel_name, url_list in channel_groups.items():
                # 按速度从高到低排序
                url_list.sort(key=lambda x: -float(x[2]))
                # 限制每个频道最多RESULTS_PER_CHANNEL个URL
                url_list = url_list[:RESULTS_PER_CHANNEL]
                grouped_channels.extend(url_list)
            
            # 按频道名称排序
            grouped_channels.sort(key=lambda x: x[0])
            processed_categories[category] = grouped_channels
    
    return processed_categories

# 获取酒店源流程        
def hotel_iptv(config_file):
    # 先检测并更新IP文件
    available_ips = check_and_update_ip_file(config_file)
    
    if not available_ips:
        print(f"没有可用的IP，跳过 {config_file}")
        return
    
    ip_configs = read_config(config_file)
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
    
    # 修复：测速后检查是否有可用频道
    if not results:
        print(f"⚠️ 警告：IP检测通过但所有频道都不可用，将该IP视为不可用")
        print(f"🗑️ 从 {config_file} 中删除该IP")
        
        # 清空IP文件
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write("")
        
        print(f"✓ 已清空 {config_file}（没有可用的频道）")
        return
    else:
        print(f"✓ 找到 {len(results)} 个可用频道，IP保持有效")
    
    # 对频道进行排序和统一名称（原有逻辑）
    results.sort(key=lambda x: -float(x[2]))
    results.sort(key=lambda x: channel_key(x[0]))
    
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
    
    # 对分类后的数据进行分组和排序处理
    processed_categories = group_and_sort_channels_by_category(categorized)
    
    # 写入分类文件
    file_paths = []
    for category, channels in processed_categories.items():
        if channels:
            # 写入文件
            filename = f"{category.replace('频道', '')}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"{category},#genre#\n")
                for name, url, speed in channels:
                    f.write(f"{name},{url}\n")
            
            file_paths.append(filename)
            print(f"已保存 {len(channels)} 个频道到 {filename}")
    
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
    main()
