import requests
import os
import time
from typing import List, Tuple
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 组播流配置
CITY_STREAMS = {
    "安徽电信": ["rtp/238.1.79.27:4328"],
    "北京市电信": ["rtp/225.1.8.21:8002"],
    "北京市联通": ["rtp/239.3.1.241:8000"],
    "江苏电信": ["udp/239.49.8.19:9614"],
    "四川电信": ["udp/239.93.0.169:5140"],
    "四川移动": ["rtp/239.11.0.78:5140"],
    "四川联通": ["rtp/239.0.0.1:5140"],
    "上海市电信": ["rtp/239.45.3.146:5140"],
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
    "河北电信": ["rtp/239.254.200.174:6000"],
    "河北联通": ["rtp/239.253.92.154:6011"],
    "河南电信": ["rtp/239.16.20.21:10210"],    
    "河南联通": ["rtp/225.1.4.98:1127"],
    "浙江电信": ["udp/233.50.201.100:5140"],
    "海南电信": ["rtp/239.253.64.253:5140"],
    "海南联通": ["rtp/239.254.96.179:7154"],
    "湖北电信": ["rtp/239.254.96.115:8664"],
    "湖北联通": ["rtp/228.0.0.60:6108"],
    "湖南电信": ["udp/239.76.253.101:9000"],
    "甘肃电信": ["udp/239.255.30.249:8231"],
    "福建电信": ["rtp/239.61.2.132:8708"],
    "福建联通": ["rtp/239.255.40.149:8208"],
    "贵州电信": ["rtp/238.255.2.1:5999"],
    "辽宁联通": ["rtp/232.0.0.126:1234"],
    "重庆市电信": ["rtp/235.254.196.249:1268"],
    "重庆市联通": ["udp/225.0.4.187:7980"],
    "陕西电信": ["rtp/239.111.205.35:5140"],
    "青海电信": ["rtp/239.120.1.64:8332"],
    "黑龙江联通": ["rtp/229.58.190.150:5000"],

}


def read_ip_file(filepath: str) -> List[str]:
    """读取IP文件"""
    ips = []
    if not os.path.exists(filepath):
        logger.warning(f"文件不存在: {filepath}")
        return ips
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and ':' in line:
                    ips.append(line)
    except Exception as e:
        logger.error(f"读取文件失败: {e}")
    
    return ips


def test_single_url(url: str, timeout: int = 3) -> Tuple[float, str]:
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


def process_city_simple(city: str, streams: List[str]):
    """简化版的城市处理函数"""
    logger.info(f"处理: {city}")
    
    # 读取IP
    ip_file = f"IP_Scan/ip/{city}_good_ip.txt"
    ips = read_ip_file(ip_file)
    
    if not ips:
        logger.warning(f"无IP地址: {ip_file}")
        return
    
    logger.info(f"找到 {len(ips)} 个IP")
    
    # 测试所有IP
    results = []
    
    for ip in ips:
        for stream in streams:
            url = f"http://{ip}/{stream}"
            speed, error = test_single_url(url)
            
            if error:
                logger.debug(f"测试失败 {ip}: {error}")
            else:
                results.append((ip, speed))
                logger.info(f"测试成功 {ip}: {speed:.2f} KB/s")
                break  # 成功一个就继续下一个IP
    
    # 排序并取前2
    results.sort(key=lambda x: x[1], reverse=True)
    top_ips = results[:2]
    
    if not top_ips:
        logger.warning(f"无有效IP: {city}")
        return
    
    # 保存结果
    os.makedirs("IP_Scan/result_ip", exist_ok=True)
    output_file = f"IP_Scan/result_ip/{city}.txt"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for ip, speed in top_ips:
            f.write(f"{ip}\n")
            logger.info(f"保存: {ip} (速度: {speed:.2f} KB/s)")
    
    logger.info(f"结果已保存: {output_file}")


def main_simple():
    """简化版主函数"""
    logger.info("开始组播流测速...")
    
    for city, streams in CITY_STREAMS.items():
        try:
            process_city_simple(city, streams)
        except Exception as e:
            logger.error(f"处理 {city} 错误: {e}")
    
    logger.info("测速完成！")


if __name__ == "__main__":
    # 使用简化版
    main_simple()
