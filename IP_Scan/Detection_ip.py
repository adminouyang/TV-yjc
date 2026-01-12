import requests
import os
import time
from typing import List, Tuple, Set, Dict
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
                if line and not line.startswith('#') and ':' in line:
                    ips.append(line)
    except Exception as e:
        logger.error(f"读取文件失败: {e}")
    
    return ips


def write_ip_file(filepath: str, ips: List[str]):
    """写入IP文件"""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            for ip in ips:
                f.write(f"{ip}\n")
    except Exception as e:
        logger.error(f"写入文件失败 {filepath}: {e}")


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


def test_ip_with_streams(ip: str, streams: List[str]) -> Tuple[bool, float, str]:
    """测试单个IP的所有流，返回是否成功、速度和使用的流地址"""
    ip_speed = 0
    used_stream = ""
    
    for stream in streams:
        url = f"http://{ip}/{stream}"
        speed, error = test_single_url(url)
        
        if error:
            logger.debug(f"{ip} 测试失败: {error} (流: {stream})")
        else:
            ip_speed = speed
            used_stream = stream
            logger.info(f"{ip} 测试成功: {speed:.2f} KB/s (流: {stream})")
            return True, ip_speed, used_stream
    
    # 如果所有流都失败
    logger.info(f"{ip} 所有流测试失败")
    return False, 0, ""


def process_city(city: str, streams: List[str]):
    """处理单个城市/运营商的测试"""
    logger.info(f"开始处理: {city}")
    
    successful_ips = []  # 存储(ip, speed, stream)元组
    failed_ips = set()   # 存储失败的IP
    
    # 1. 首先测试上一次保存的最快IP
    result_file = f"IP_Scan/result_ip/{city}.txt"
    previous_fast_ips = read_ip_file(result_file)
    
    if previous_fast_ips:
        logger.info(f"找到上一次的最快IP: {len(previous_fast_ips)} 个")
        for ip in previous_fast_ips:
            success, speed, stream = test_ip_with_streams(ip, streams)
            if success:
                successful_ips.append((ip, speed, stream))
                logger.info(f"上一次的IP {ip} 仍然有效: {speed:.2f} KB/s")
            else:
                failed_ips.add(ip)
                logger.info(f"上一次的IP {ip} 已失效")
    
    # 2. 如果上一次的IP不足2个有效，从原始文件中测试更多IP
    if len(successful_ips) < 2:
        # 读取原始IP文件
        ip_file = f"IP_Scan/ip/{city}.txt"
        all_ips = read_ip_file(ip_file)
        
        if not all_ips:
            logger.warning(f"无原始IP地址: {ip_file}")
        else:
            logger.info(f"从原始文件读取到 {len(all_ips)} 个IP")
            
            # 排除已经测试过的IP（包括成功和失败的）
            remaining_ips = [ip for ip in all_ips if ip not in [item[0] for item in successful_ips] and ip not in failed_ips]
            logger.info(f"需要测试的新IP: {len(remaining_ips)} 个")
            
            # 测试剩余的IP
            for ip in remaining_ips:
                if len(successful_ips) >= 2:
                    break  # 已经有2个成功的IP，停止测试
                    
                success, speed, stream = test_ip_with_streams(ip, streams)
                if success:
                    successful_ips.append((ip, speed, stream))
                else:
                    failed_ips.add(ip)
    
    # 3. 从原始IP文件中删除失败的IP
    ip_file = f"IP_Scan/ip/{city}.txt"
    all_ips = read_ip_file(ip_file)
    if all_ips and failed_ips:
        # 从原始IP列表中移除失败的IP
        original_count = len(all_ips)
        all_ips = [ip for ip in all_ips if ip not in failed_ips]
        remaining_count = len(all_ips)
        
        if remaining_count > 0:
            write_ip_file(ip_file, all_ips)
            logger.info(f"{city} - 从原始文件中删除 {original_count - remaining_count} 个失败IP，剩余 {remaining_count} 个IP")
        else:
            # 如果所有IP都失败，保留原文件但写入注释
            write_ip_file(ip_file, ["# 所有IP测试失败，请检查网络或重新扫描"])
            logger.warning(f"{city} - 所有IP测试失败，文件已清空")
    
    # 4. 保存最快的2个IP到结果文件
    os.makedirs("IP_Scan/result_ip", exist_ok=True)
    output_file = f"IP_Scan/result_ip/{city}.txt"
    
    if successful_ips:
        # 按速度排序并取前2
        successful_ips.sort(key=lambda x: x[1], reverse=True)
        top_ips = successful_ips[:2]
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for ip, speed, stream in top_ips:
                f.write(f"{ip}\n")
                logger.info(f"{city} - 保存最快IP: {ip} (速度: {speed:.2f} KB/s, 流: {stream})")
        
        logger.info(f"{city} - 结果已保存: {output_file}")
    else:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# {city} 无可用IP\n")
        logger.warning(f"{city} - 无可用IP，已保存空结果")


def main():
    """主函数"""
    logger.info("开始组播流测速并清理失败IP...")
    
    for city, streams in CITY_STREAMS.items():
        try:
            process_city(city, streams)
        except Exception as e:
            logger.error(f"处理 {city} 错误: {e}")
    
    logger.info("测速完成！")


if __name__ == "__main__":
    main()
