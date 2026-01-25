import os
import re
import requests
import time
import json
import concurrent.futures
import hashlib
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import pickle
import base64
import random

# ===============================
# 配置区
# ===============================

# 默认配置
DEFAULT_CONFIG = {
    "fofa": {
        "email": "",
        "password": "",
        "api_key": "",
        "max_pages": 5,
        "page_size": 20
    },
    "zoomeye": {
        "username": "",
        "password": "",
        "api_key": ""
    }
}

# 配置文件和cookie文件路径
CONFIG_DIR = "Hotel"
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
COOKIE_FILE = os.path.join(CONFIG_DIR, "fofa_cookies.pkl")
SESSION_FILE = os.path.join(CONFIG_DIR, "session_state.pkl")

# IP存储目录
IP_DIR = "Hotel/ip"

# User-Agent列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
]

# 搜索关键词（base64编码）
SEARCH_QUERIES = [
    "ImlwdHYvbGl2ZS96aF9jbi5qcyIgJiYgY291bnRyeT0iQ04i",  # IPTV直播
    "InVkcHh5IiAmJiBjb3VudHJ5PSJDTiI=",  # UDPXY
    "ImlwdHYvbGl2ZSIgJiYgY291bnRyeT0iQ04i",  # IPTV直播通用
    "ImlwdHYiICYmIGNvdW50cnk9IkNOIg==",  # IPTV
    "cG9ydD0iODA4MCIgJiYgY291bnRyeT0iQ04i",  # 端口8080
    "dGl0bGU9ImlwdHYiICYmIGNvdW50cnk9IkNOIg=="  # 标题包含IPTV
]

# 创建必要的目录
for directory in [CONFIG_DIR, IP_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# ===============================
# 配置管理
# ===============================

class ConfigManager:
    def __init__(self):
        self.config = self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 合并默认配置
                    for key in DEFAULT_CONFIG:
                        if key in config:
                            DEFAULT_CONFIG[key].update(config[key])
                        else:
                            config[key] = DEFAULT_CONFIG[key]
                    return config
            except Exception as e:
                print(f"❌ 加载配置文件失败: {e}")
                print("📄 使用默认配置...")
        
        # 创建默认配置文件
        self.create_default_config()
        return DEFAULT_CONFIG.copy()
    
    def create_default_config(self):
        """创建默认配置文件"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
            print(f"📄 已创建配置文件: {CONFIG_FILE}")
            print("⚠️ 请编辑配置文件，填入正确的登录信息")
        except Exception as e:
            print(f"❌ 创建配置文件失败: {e}")
    
    def get_fofa_config(self):
        """获取FOFA配置"""
        return self.config.get("fofa", {})
    
    def get_zoomeye_config(self):
        """获取ZoomEye配置"""
        return self.config.get("zoomeye", {})

# ===============================
# 登录管理器
# ===============================

class LoginManager:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        })
        self.is_logged_in = False
        self.login_method = None
    
    def get_headers(self):
        """获取随机User-Agent的headers"""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        }
    
    def save_cookies(self, cookies):
        """保存cookies到文件"""
        try:
            with open(COOKIE_FILE, 'wb') as f:
                pickle.dump(cookies, f)
            print("💾 Cookies已保存")
        except Exception as e:
            print(f"❌ 保存cookies失败: {e}")
    
    def load_cookies(self):
        """从文件加载cookies"""
        if os.path.exists(COOKIE_FILE):
            try:
                with open(COOKIE_FILE, 'rb') as f:
                    cookies = pickle.load(f)
                print("📂 从文件加载cookies")
                return cookies
            except Exception as e:
                print(f"❌ 加载cookies失败: {e}")
        return None
    
    def save_session_state(self):
        """保存会话状态"""
        try:
            session_state = {
                'cookies': self.session.cookies.get_dict(),
                'headers': dict(self.session.headers),
                'timestamp': datetime.now().timestamp()
            }
            with open(SESSION_FILE, 'wb') as f:
                pickle.dump(session_state, f)
        except Exception as e:
            print(f"❌ 保存会话状态失败: {e}")
    
    def load_session_state(self):
        """加载会话状态"""
        if os.path.exists(SESSION_FILE):
            try:
                with open(SESSION_FILE, 'rb') as f:
                    session_state = pickle.load(f)
                
                # 检查是否过期（24小时）
                if datetime.now().timestamp() - session_state.get('timestamp', 0) < 24 * 3600:
                    self.session.cookies.update(session_state.get('cookies', {}))
                    self.session.headers.update(session_state.get('headers', {}))
                    print("📂 从文件加载会话状态")
                    return True
            except Exception as e:
                print(f"❌ 加载会话状态失败: {e}")
        return False
    
    def login_fofa(self):
        """登录FOFA（多方法尝试）"""
        config = self.config_manager.get_fofa_config()
        
        # 方法1: 使用API Key
        if config.get("api_key"):
            print("🔐 尝试使用API Key登录FOFA...")
            self.session.headers.update({
                "Authorization": f"Bearer {config['api_key']}"
            })
            if self._check_fofa_login():
                self.is_logged_in = True
                self.login_method = "api_key"
                print("✅ 使用API Key登录成功")
                return True
        
        # 方法2: 使用cookies登录
        if self._login_fofa_with_cookies():
            return True
        
        # 方法3: 使用Selenium登录
        if config.get("email") and config.get("password"):
            print("🔐 尝试使用Selenium登录FOFA...")
            if self._login_fofa_selenium():
                return True
        
        print("⚠️ 所有登录方法都失败了，将以未登录状态爬取（可能结果有限）")
        return False
    
    def _login_fofa_with_cookies(self):
        """使用cookies登录FOFA"""
        print("🔐 尝试使用cookies登录FOFA...")
        
        # 尝试加载会话状态
        if self.load_session_state():
            if self._check_fofa_login():
                self.is_logged_in = True
                self.login_method = "cookies"
                print("✅ 使用会话状态登录成功")
                return True
        
        # 尝试加载保存的cookies
        cookies = self.load_cookies()
        if cookies:
            if isinstance(cookies, list):  # Selenium格式的cookies
                for cookie in cookies:
                    self.session.cookies.set(cookie['name'], cookie['value'])
            elif isinstance(cookies, dict):  # Requests格式的cookies
                self.session.cookies.update(cookies)
            
            if self._check_fofa_login():
                self.is_logged_in = True
                self.login_method = "cookies"
                print("✅ 使用cookies登录成功")
                return True
        
        return False
    
    def _login_fofa_selenium(self):
        """使用Selenium登录FOFA"""
        config = self.config_manager.get_fofa_config()
        
        # 设置Chrome选项
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # 无头模式
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')
        
        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.get("https://fofa.info/login")
            
            # 等待页面加载
            time.sleep(3)
            
            # 查找邮箱输入框
            email_input = driver.find_element(By.NAME, "email")
            email_input.clear()
            email_input.send_keys(config["email"])
            time.sleep(1)
            
            # 查找密码输入框
            password_input = driver.find_element(By.NAME, "password")
            password_input.clear()
            password_input.send_keys(config["password"])
            time.sleep(1)
            
            # 查找登录按钮并点击
            login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            time.sleep(5)
            
            # 检查登录是否成功
            if "login" not in driver.current_url.lower():
                # 获取cookies
                cookies = driver.get_cookies()
                self.save_cookies(cookies)
                
                # 更新requests session的cookies
                for cookie in cookies:
                    self.session.cookies.set(cookie['name'], cookie['value'])
                
                # 保存会话状态
                self.save_session_state()
                
                self.is_logged_in = True
                self.login_method = "selenium"
                print("✅ Selenium登录FOFA成功")
                
                driver.quit()
                return True
            else:
                print("❌ Selenium登录失败")
                driver.quit()
                return False
                
        except Exception as e:
            print(f"❌ Selenium登录失败: {e}")
            return False
    
    def _check_fofa_login(self):
        """检查FOFA登录状态"""
        try:
            test_url = "https://fofa.info/user/users"
            response = self.session.get(test_url, timeout=10, headers=self.get_headers())
            
            # 检查是否跳转到登录页面
            if "login" in response.url.lower() or "登录" in response.text:
                return False
            
            # 检查是否有用户信息
            if "user-info" in response.text or "我的资产" in response.text:
                return True
                
            return response.status_code == 200 and "访问限制" not in response.text
            
        except Exception as e:
            print(f"⚠️ 检查登录状态失败: {e}")
            return False
    
    def get_session(self):
        """获取登录后的session"""
        return self.session

# ===============================
# IP处理函数
# ===============================

def get_isp(ip):
    """IP运营商判断"""
    # 电信IP段
    telecom_pattern = r"^(1\.(0|1[0-9]{2}|2[0-5]?[0-9]?)\.|14\.[0-9]{1,3}\.|27\.[0-9]{1,3}\.|36\.[0-9]{1,3}\.|39\.[0-9]{1,3}\.|42\.[0-9]{1,3}\.|49\.[0-9]{1,3}\.|58\.[0-9]{1,3}\.|60\.[0-9]{1,3}\.|101\.[0-9]{1,3}\.|106\.[0-9]{1,3}\.|110\.[0-9]{1,3}\.|111\.[0-9]{1,3}\.|112\.[0-9]{1,3}\.|113\.[0-9]{1,3}\.|115\.[0-9]{1,3}\.|116\.[0-9]{1,3}\.|117\.[0-9]{1,3}\.|118\.[0-9]{1,3}\.|119\.[0-9]{1,3}\.|120\.[0-9]{1,3}\.|121\.[0-9]{1,3}\.|122\.[0-9]{1,3}\.|123\.[0-9]{1,3}\.|124\.[0-9]{1,3}\.|125\.[0-9]{1,3}\.|171\.[8-9][0-9]\.|171\.[1-9][0-9]{2}\.|175\.[0-9]{1,3}\.|182\.[0-9]{1,3}\.|183\.[0-9]{1,3}\.|202\.[0-9]{1,3}\.|203\.[0-9]{1,3}\.|210\.[0-9]{1,3}\.|211\.[0-9]{1,3}\.|218\.[0-9]{1,3}\.|219\.[0-9]{1,3}\.|220\.[0-9]{1,3}\.|221\.[0-9]{1,3}\.|222\.[0-9]{1,3}\.)"
    
    # 联通IP段
    unicom_pattern = r"^(42\.1[0-9]{0,2}\.|43\.[0-9]{1,3}\.|58\.[2-5][0-9]\.|59\.[0-9]{1,3}\.|60\.[0-9]{1,3}\.|61\.[0-9]{1,3}\.|110\.[0-9]{1,3}\.|111\.[0-9]{1,3}\.|112\.[0-9]{1,3}\.|113\.[0-9]{1,3}\.|114\.[0-9]{1,3}\.|115\.[0-9]{1,3}\.|116\.[0-9]{1,3}\.|117\.[0-9]{1,3}\.|118\.[0-9]{1,3}\.|119\.[0-9]{1,3}\.|120\.[0-9]{1,3}\.|121\.[0-9]{1,3}\.|122\.[0-9]{1,3}\.|123\.[0-9]{1,3}\.|124\.[0-9]{1,3}\.|125\.[0-9]{1,3}\.|171\.[8-9][0-9]\.|171\.[1-9][0-9]{2}\.|175\.[0-9]{1,3}\.|182\.[0-9]{1,3}\.|183\.[0-9]{1,3}\.|210\.[0-9]{1,3}\.|211\.[0-9]{1,3}\.|218\.[0-9]{1,3}\.|219\.[0-9]{1,3}\.|220\.[0-9]{1,3}\.|221\.[0-9]{1,3}\.|222\.[0-9]{1,3}\.)"
    
    # 移动IP段
    mobile_pattern = r"^(36\.[0-9]{1,3}\.|37\.[0-9]{1,3}\.|38\.[0-9]{1,3}\.|39\.[0-9]{1,3}\.|42\.2[0-9]{0,2}\.|42\.3[0-9]{0,2}\.|47\.[0-9]{1,3}\.|106\.[0-9]{1,3}\.|111\.[0-9]{1,3}\.|112\.[0-9]{1,3}\.|113\.[0-9]{1,3}\.|114\.[0-9]{1,3}\.|115\.[0-9]{1,3}\.|116\.[0-9]{1,3}\.|117\.[0-9]{1,3}\.|118\.[0-9]{1,3}\.|119\.[0-9]{1,3}\.|120\.[0-9]{1,3}\.|121\.[0-9]{1,3}\.|122\.[0-9]{1,3}\.|123\.[0-9]{1,3}\.|124\.[0-9]{1,3}\.|125\.[0-9]{1,3}\.|134\.[0-9]{1,3}\.|135\.[0-9]{1,3}\.|136\.[0-9]{1,3}\.|137\.[0-9]{1,3}\.|138\.[0-9]{1,3}\.|139\.[0-9]{1,3}\.|150\.[0-9]{1,3}\.|151\.[0-9]{1,3}\.|152\.[0-9]{1,3}\.|157\.[0-9]{1,3}\.|158\.[0-9]{1,3}\.|159\.[0-9]{1,3}\.|170\.[0-9]{1,3}\.|178\.[0-9]{1,3}\.|182\.[0-9]{1,3}\.|183\.[0-9]{1,3}\.|184\.[0-9]{1,3}\.|187\.[0-9]{1,3}\.|188\.[0-9]{1,3}\.|189\.[0-9]{1,3}\.)"
    
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
        
        # 尝试多个IP查询API
        apis = [
            f"http://ip-api.com/json/{ip}?lang=zh-CN",
            f"https://ipapi.co/{ip}/json/",
            f"http://ipwho.is/{ip}"
        ]
        
        for api_url in apis:
            try:
                response = requests.get(api_url, timeout=5, headers={"User-Agent": random.choice(USER_AGENTS)})
                if response.status_code == 200:
                    data = response.json()
                    
                    if api_url.startswith("http://ip-api.com"):
                        if data.get("status") == "success":
                            province = data.get("regionName", "未知")
                            isp = get_isp(ip)
                            return province, isp, ip_port
                    
                    elif api_url.startswith("https://ipapi.co"):
                        if "region" in data:
                            province = data.get("region", "未知")
                            isp = get_isp(ip)
                            return province, isp, ip_port
                    
                    elif api_url.startswith("http://ipwho.is"):
                        if "success" in data and data["success"]:
                            province = data.get("region", "未知")
                            isp = get_isp(ip)
                            return province, isp, ip_port
                            
            except Exception:
                continue
        
        # 如果所有API都失败，返回未知
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
                    ip = line.strip()
                    if ip and "#" not in ip:  # 跳过注释行
                        existing_ips.add(ip)
            print(f"📖 从 {os.path.basename(filepath)} 读取到 {len(existing_ips)} 个现有IP")
        except Exception as e:
            print(f"❌ 读取文件 {filepath} 失败: {e}")
    return existing_ips

def generate_fofa_urls(config):
    """生成FOFA搜索URL"""
    urls = []
    pages = config.get("max_pages", 5)
    page_size = config.get("page_size", 20)
    
    for query in SEARCH_QUERIES:
        for page in range(1, pages + 1):
            url = f"https://fofa.info/result?qbase64={query}&page={page}&page_size={page_size}"
            urls.append(url)
    
    return urls

# ===============================
# 爬取和分类
# ===============================

def crawl_fofa(login_manager):
    """爬取FOFA数据"""
    config = login_manager.config_manager.get_fofa_config()
    session = login_manager.get_session()
    
    all_ips = set()
    fofa_urls = generate_fofa_urls(config)
    
    print(f"🔍 开始爬取FOFA，共 {len(fofa_urls)} 个页面")
    
    for i, url in enumerate(fofa_urls, 1):
        print(f"📡 正在爬取第 {i}/{len(fofa_urls)} 页...")
        
        try:
            # 随机延迟，避免请求过快
            time.sleep(random.uniform(1, 3))
            
            # 使用随机User-Agent
            headers = login_manager.get_headers()
            response = session.get(url, timeout=15, headers=headers)
            
            if response.status_code == 403 or "访问限制" in response.text or "请登录" in response.text:
                print(f"❌ 第 {i} 页访问被限制，尝试重新登录...")
                if login_manager.login_fofa():
                    session = login_manager.get_session()
                    response = session.get(url, timeout=15, headers=headers)
                else:
                    print(f"⚠️ 登录失败，跳过第 {i} 页")
                    continue
            
            if response.status_code != 200:
                print(f"❌ 第 {i} 页请求失败，状态码: {response.status_code}")
                continue
            
            # 多种正则表达式匹配IP
            ip_patterns = [
                r'<a[^>]*href="[^"]*?//(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5})"',  # IP:端口
                r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5})',  # 通用IP:端口
                r'ip.*?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*?port.*?(\d{2,5})',  # IP和端口分开
                r'host.*?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*?port.*?(\d{2,5})'  # host和port
            ]
            
            page_ips = set()
            for pattern in ip_patterns:
                matches = re.findall(pattern, response.text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        ip_port = f"{match[0]}:{match[1]}"
                    else:
                        ip_port = match
                    
                    # 验证IP和端口格式
                    ip_match = re.match(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{2,5})', ip_port)
                    if ip_match:
                        # 验证IP地址的每个部分
                        ip_parts = ip_match.group(1).split('.')
                        if all(0 <= int(part) <= 255 for part in ip_parts):
                            # 验证端口
                            port = int(ip_match.group(2))
                            if 1 <= port <= 65535:
                                page_ips.add(ip_port)
            
            all_ips.update(page_ips)
            print(f"✅ 第 {i} 页获取到 {len(page_ips)} 个IP，当前总数 {len(all_ips)}")
            
        except Exception as e:
            print(f"❌ 第 {i} 页爬取失败: {e}")
    
    print(f"🎯 FOFA爬取完成，总共获取到 {len(all_ips)} 个有效IP")
    return all_ips

def process_and_save_ips(ip_list):
    """处理IP并保存到文件"""
    if not ip_list:
        print("⚠️ 没有获取到IP，跳过处理")
        return
    
    print(f"🔧 开始处理 {len(ip_list)} 个IP...")
    
    # 使用多线程加速IP信息查询
    province_isp_dict = {}
    processed_count = 0
    total_count = len(ip_list)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_ip = {executor.submit(get_ip_info, ip): ip for ip in ip_list}
        
        for i, future in enumerate(concurrent.futures.as_completed(future_to_ip), 1):
            province, isp, ip_port = future.result()
            
            if province and isp and isp != "未知":
                # 清理省份名称（移除"省"、"市"等）
                province_clean = province.replace("省", "").replace("市", "").replace("自治区", "").replace("特别行政区", "")
                fname = f"{province_clean}{isp}.txt"
                province_isp_dict.setdefault(fname, set()).add(ip_port)
            
            processed_count += 1
            if processed_count % 100 == 0 or processed_count == total_count:
                print(f"⏳ 已处理 {processed_count}/{total_count} 个IP...")
    
    # 保存到文件
    total_saved = 0
    for fname, ips in province_isp_dict.items():
        filepath = os.path.join(IP_DIR, fname)
        existing_ips = read_existing_ips(filepath)
        
        # 去重
        new_ips = ips - existing_ips
        
        if new_ips:
            # 追加模式写入
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(f"\n# 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                for ip in sorted(new_ips):
                    f.write(ip + '\n')
            
            total_saved += len(new_ips)
            print(f"💾 已保存 {len(new_ips)} 个新IP到 {fname}")
    
    # 生成汇总文件
    generate_summary(province_isp_dict)
    
    print(f"✅ IP处理完成！共保存 {total_saved} 个新IP到 {len(province_isp_dict)} 个分类文件")

def generate_summary(province_isp_dict):
    """生成汇总文件"""
    summary_file = os.path.join(IP_DIR, "ip_summary.txt")
    try:
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("=" * 50 + "\n")
            f.write("IP地址汇总\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")
            
            total_ips = 0
            sorted_files = sorted(province_isp_dict.items(), key=lambda x: len(x[1]), reverse=True)
            
            for fname, ips in sorted_files:
                count = len(ips)
                total_ips += count
                f.write(f"{fname}: {count} 个IP\n")
            
            f.write("\n" + "=" * 50 + "\n")
            f.write(f"总计: {total_ips} 个IP地址\n")
            f.write("=" * 50 + "\n")
        
        print(f"📊 汇总文件已生成: {summary_file}")
        
    except Exception as e:
        print(f"❌ 生成汇总文件失败: {e}")

# ===============================
# 主函数
# ===============================

def main():
    """主函数"""
    print("=" * 60)
    print("🌐 IP地址抓取和分类工具")
    print(f"📁 配置文件: {CONFIG_FILE}")
    print(f"📁 输出目录: {IP_DIR}")
    print("=" * 60)
    
    # 初始化配置管理器
    config_manager = ConfigManager()
    
    # 初始化登录管理器
    login_manager = LoginManager(config_manager)
    
    # 尝试登录
    print("\n🔐 正在登录FOFA...")
    login_success = login_manager.login_fofa()
    
    if login_success:
        print(f"✅ 登录成功，使用方式: {login_manager.login_method}")
    else:
        print("⚠️ 登录失败，将以未登录状态爬取")
    
    # 爬取FOFA
    print("\n🚀 开始爬取FOFA数据...")
    all_ips = crawl_fofa(login_manager)
    
    if all_ips:
        # 处理并保存IP
        print("\n💾 开始处理IP地址...")
        process_and_save_ips(all_ips)
        
        # 保存会话状态
        login_manager.save_session_state()
    else:
        print("❌ 没有获取到任何IP地址")
    
    print("\n" + "=" * 60)
    print("🎉 任务完成！")
    print("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断程序")
    except Exception as e:
        print(f"\n❌ 程序运行出错: {e}")
    finally:
        print("👋 程序结束")
