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
        chunk_size = 4096
        max_size = 1024 * 1024  # 最多下载1MB
        
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                downloaded += len(chunk)
            
            if downloaded >= chunk_size * 10:  # 下载大约40KB就够判断速度了
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
