import requests
import os
import time
import json
import concurrent.futures
from typing import List, Tuple, Dict, Set, Optional
import logging
from dataclasses import dataclass
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import signal
import sys

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'ip_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
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

# 配置参数
CONFIG = {
    'timeout': 5,  # 超时时间
    'max_workers': 20,  # 最大并发线程数
    'max_retries': 2,  # 重试次数
    'chunk_size': 102400,  # 每次下载块大小
    'max_download_size': 1024 * 1024,  # 最大下载大小 1MB
    'min_speed_kbps': 10,  # 最小速度阈值(KB/s)
    'result_dir': 'IP_Scan/result_ip',
    'ip_dir': 'IP_Scan/ip',
    'backup_dir': 'IP_Scan/backup',
    'cache_dir': '.cache',
    'max_test_per_city': 50,  # 每个城市最大测试IP数量
}

# 信号处理
shutdown_flag = False
def signal_handler(signum, frame):
    global shutdown_flag
    shutdown_flag = True
    logger.info("收到停止信号，正在保存当前进度...")

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

@dataclass
class TestResult:
    """测试结果数据类"""
    ip: str
    speed_kbps: float
    stream: str
    success: bool
    error_msg: str = ""
    timestamp: float = 0.0

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
            # 配置session
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=100,
                pool_maxsize=100,
                max_retries=self.config.get('max_retries', 2)
            )
            self.session.mount('http://', adapter)
            self.session.mount('https://', adapter)
        return self.session
    
    def normalize_stream_url(self, ip: str, stream: str) -> str:
        """标准化流URL"""
        # 去除协议前缀，统一使用http
        if stream.startswith(('rtp/', 'udp/')):
            # 提取IP:端口部分
            stream_addr = stream.split('/')[1]
            return f"http://{ip}/{stream_addr}"
        return f"http://{ip}/{stream}"
    
    def read_ip_file(self, filepath: str) -> List[str]:
        """读取IP文件"""
        ips = []
        if not os.path.exists(filepath):
            logger.warning(f"文件不存在: {filepath}")
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
            logger.error(f"读取文件 {filepath} 失败: {e}")
        
        return ips
    
    def write_ip_file(self, filepath: str, ips: List[str], backup: bool = True):
        """写入IP文件，可选备份"""
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # 备份原始文件
            if backup and os.path.exists(filepath):
                backup_dir = os.path.join(self.config['backup_dir'], 
                                        os.path.basename(os.path.dirname(filepath)))
                os.makedirs(backup_dir, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = os.path.join(backup_dir, 
                                          f"{os.path.basename(filepath)}_{timestamp}.bak")
                import shutil
                shutil.copy2(filepath, backup_file)
                logger.debug(f"已备份文件: {backup_file}")
            
            with open(filepath, 'w', encoding='utf-8') as f:
                for ip in ips:
                    f.write(f"{ip}\n")
            return True
        except Exception as e:
            logger.error(f"写入文件 {filepath} 失败: {e}")
            return False
    
    def test_single_url(self, ip: str, stream: str) -> TestResult:
        """测试单个URL的速度"""
        url = self.normalize_stream_url(ip, stream)
        result = TestResult(
            ip=ip,
            speed_kbps=0,
            stream=stream,
            success=False,
            timestamp=time.time()
        )
        
        try:
            session = self.get_session()
            start_time = time.time()
            
            with session.get(
                url, 
                timeout=self.config['timeout'], 
                stream=True,
                headers={'User-Agent': 'Mozilla/5.0'}
            ) as response:
                
                if response.status_code != 200:
                    result.error_msg = f"HTTP {response.status_code}"
                    return result
                
                # 下载数据测试速度
                downloaded = 0
                for chunk in response.iter_content(
                    chunk_size=self.config['chunk_size']
                ):
                    if not chunk or shutdown_flag:
                        break
                    
                    downloaded += len(chunk)
                    if downloaded >= self.config['max_download_size']:
                        break
                
                elapsed = time.time() - start_time
                if elapsed > 0:
                    speed_kbps = (downloaded / 1024) / elapsed
                    if speed_kbps >= self.config['min_speed_kbps']:
                        result.speed_kbps = speed_kbps
                        result.success = True
                    else:
                        result.error_msg = f"速度过低: {speed_kbps:.2f} KB/s"
                else:
                    result.error_msg = "time error"
                        
        except requests.exceptions.Timeout:
            result.error_msg = "timeout"
        except requests.exceptions.ConnectionError:
            result.error_msg = "connection error"
        except Exception as e:
            result.error_msg = str(e)
        
        return result
    
    def test_ip_with_streams(self, ip: str, streams: List[str]) -> TestResult:
        """测试单个IP的所有流，返回最佳结果"""
        best_result = None
        
        for stream in streams:
            if shutdown_flag:
                break
                
            result = self.test_single_url(ip, stream)
            
            if result.success:
                if best_result is None or result.speed_kbps > best_result.speed_kbps:
                    best_result = result
                # 如果速度足够好，提前返回
                if result.speed_kbps > 1000:  # 1MB/s以上的速度就很好了
                    break
        
        if best_result is None:
            # 所有流都失败，返回第一个错误
            result = self.test_single_url(ip, streams[0])
            return result
        else:
            return best_result
    
    def process_city_ips(self, city: str, 
                        result_ips: List[str], 
                        original_ips: List[str],
                        streams: List[str]) -> Dict:
        """处理单个城市的IP测试"""
        logger.info(f"开始处理城市: {city}")
        logger.info(f"结果IP文件有 {len(result_ips)} 个IP")
        logger.info(f"原始IP文件有 {len(original_ips)} 个IP")
        
        all_results = []
        tested_ips = set()
        valid_ips = []
        
        # 1. 测试result_ip文件中的IP
        if result_ips:
            logger.info(f"开始测试结果IP文件中的IP...")
            result_ips_to_test = result_ips[:self.config['max_test_per_city']]
            
            with ThreadPoolExecutor(max_workers=self.config['max_workers']) as executor:
                future_to_ip = {
                    executor.submit(self.test_ip_with_streams, ip, streams): ip 
                    for ip in result_ips_to_test
                }
                
                for future in as_completed(future_to_ip):
                    ip = future_to_ip[future]
                    try:
                        result = future.result()
                        all_results.append(result)
                        tested_ips.add(ip)
                        
                        if result.success:
                            self.stats['successful'] += 1
                            logger.info(f"✓ {city} - {ip}: {result.speed_kbps:.2f} KB/s "
                                      f"(流: {result.stream.split('/')[-1]})")
                        else:
                            self.stats['failed'] += 1
                            logger.warning(f"✗ {city} - {ip}: {result.error_msg}")
                            
                    except Exception as e:
                        logger.error(f"测试IP {ip} 时发生错误: {e}")
                        self.stats['failed'] += 1
        
        # 2. 测试原始IP文件中的IP（排除已测试的）
        if original_ips and not shutdown_flag:
            # 过滤掉已经测试过的IP
            remaining_ips = [
                ip for ip in original_ips 
                if ip not in tested_ips
            ][:self.config['max_test_per_city']]
            
            if remaining_ips:
                logger.info(f"开始测试原始IP文件中的IP，共{len(remaining_ips)}个...")
                
                with ThreadPoolExecutor(max_workers=self.config['max_workers']) as executor:
                    future_to_ip = {
                        executor.submit(self.test_ip_with_streams, ip, streams): ip 
                        for ip in remaining_ips
                    }
                    
                    for future in as_completed(future_to_ip):
                        if shutdown_flag:
                            break
                            
                        ip = future_to_ip[future]
                        try:
                            result = future.result()
                            all_results.append(result)
                            tested_ips.add(ip)
                            
                            if result.success:
                                self.stats['successful'] += 1
                                logger.info(f"✓ {city} - {ip}: {result.speed_kbps:.2f} KB/s "
                                          f"(流: {result.stream.split('/')[-1]})")
                            else:
                                self.stats['failed'] += 1
                                logger.warning(f"✗ {city} - {ip}: {result.error_msg}")
                                
                        except Exception as e:
                            logger.error(f"测试IP {ip} 时发生错误: {e}")
                            self.stats['failed'] += 1
        
        # 3. 筛选有效IP并排序
        valid_results = [r for r in all_results if r.success]
        valid_results.sort(key=lambda x: x.speed_kbps, reverse=True)
        
        # 提取IP地址列表
        valid_ips = [r.ip for r in valid_results]
        
        # 4. 更新原始IP文件（删除失效IP）
        if original_ips:
            # 保留未测试的IP和有效的IP
            updated_original_ips = []
            for ip in original_ips:
                if ip not in tested_ips:
                    updated_original_ips.append(ip)
                else:
                    # 检查这个IP是否有效
                    result = next((r for r in valid_results if r.ip == ip), None)
                    if result and result.success:
                        updated_original_ips.append(ip)
            
            original_file = os.path.join(self.config['ip_dir'], f"{city}.txt")
            if self.write_ip_file(original_file, updated_original_ips):
                logger.info(f"已更新原始IP文件: {len(updated_original_ips)} 个IP")
        
        # 5. 更新结果IP文件（保存所有有效IP，已排序）
        if valid_results:
            result_file = os.path.join(self.config['result_dir'], f"{city}.txt")
            
            # 保存详细结果
            detailed_results = []
            for result in valid_results:
                detailed_results.append({
                    'ip': result.ip,
                    'speed_kbps': result.speed_kbps,
                    'stream': result.stream,
                    'timestamp': result.timestamp
                })
            
            # 写入IP文件
            ip_list = [r.ip for r in valid_results]
            if self.write_ip_file(result_file, ip_list):
                logger.info(f"已保存结果: {len(ip_list)} 个有效IP到 {result_file}")
            
            # 保存详细结果到JSON
            json_file = os.path.join(self.config['result_dir'], f"{city}_details.json")
            try:
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(detailed_results, f, indent=2, ensure_ascii=False)
                logger.debug(f"详细结果已保存到: {json_file}")
            except Exception as e:
                logger.error(f"保存详细结果失败: {e}")
        
        self.stats['cities_processed'] += 1
        self.stats['total_tested'] += len(all_results)
        
        return {
            'city': city,
            'total_tested': len(all_results),
            'valid_count': len(valid_results),
            'best_speed': valid_results[0].speed_kbps if valid_results else 0,
            'valid_ips': valid_ips
        }
    
    def process_city(self, city: str, streams: List[str]) -> Optional[Dict]:
        """处理单个城市"""
        if shutdown_flag:
            return None
            
        try:
            # 确保目录存在
            os.makedirs(self.config['result_dir'], exist_ok=True)
            os.makedirs(self.config['ip_dir'], exist_ok=True)
            
            # 读取IP文件
            result_file = os.path.join(self.config['result_dir'], f"{city}.txt")
            original_file = os.path.join(self.config['ip_dir'], f"{city}.txt")
            
            result_ips = self.read_ip_file(result_file)
            original_ips = self.read_ip_file(original_file)
            
            # 处理IP测试
            return self.process_city_ips(city, result_ips, original_ips, streams)
            
        except Exception as e:
            logger.error(f"处理城市 {city} 时发生错误: {e}")
            return None
    
    def save_stats(self):
        """保存统计数据"""
        stats_file = os.path.join(self.config.get('cache_dir', '.'), 'stats.json')
        stats_data = {
            'stats': self.stats,
            'timestamp': time.time(),
            'date': datetime.now().isoformat()
        }
        
        try:
            os.makedirs(os.path.dirname(stats_file), exist_ok=True)
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存统计数据失败: {e}")
    
    def print_summary(self):
        """打印统计摘要"""
        logger.info("=" * 50)
        logger.info("测试完成！")
        logger.info(f"已处理城市: {self.stats['cities_processed']}")
        logger.info(f"总测试IP数: {self.stats['total_tested']}")
        logger.info(f"成功IP数: {self.stats['successful']}")
        logger.info(f"失败IP数: {self.stats['failed']}")
        if self.stats['total_tested'] > 0:
            success_rate = (self.stats['successful'] / self.stats['total_tested']) * 100
            logger.info(f"成功率: {success_rate:.1f}%")
        logger.info("=" * 50)

def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("组播流IP测试工具启动")
    logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"配置: 超时={CONFIG['timeout']}s, 并发数={CONFIG['max_workers']}")
    logger.info("=" * 50)
    
    # 创建管理器
    ip_manager = IPManager(CONFIG)
    
    # 处理所有城市
    all_results = []
    for city, streams in CITY_STREAMS.items():
        if shutdown_flag:
            logger.info("收到停止信号，提前结束")
            break
            
        result = ip_manager.process_city(city, streams)
        if result:
            all_results.append(result)
        
        # 每处理5个城市保存一次进度
        if len(all_results) % 5 == 0:
            ip_manager.save_stats()
    
    # 保存最终统计
    ip_manager.save_stats()
    ip_manager.print_summary()
    
    # 打印各城市结果摘要
    logger.info("\n各城市测试结果:")
    logger.info("-" * 80)
    logger.info(f"{'城市':<15} {'测试数':<8} {'有效数':<8} {'最快速度(KB/s)':<15}")
    logger.info("-" * 80)
    
    for result in all_results:
        logger.info(f"{result['city']:<15} {result['total_tested']:<8} "
                   f"{result['valid_count']:<8} {result['best_speed']:<15.2f}")
    
    logger.info("=" * 50)
    logger.info(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序运行错误: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if shutdown_flag:
            logger.info("程序已安全停止")
        sys.exit(0)
