# 修改测速函数，增加重复测速逻辑
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
                max_retries = 3  # 最大重试次数
                best_speed = 0.0
                
                for attempt in range(max_retries):
                    try:
                        channel_url_t = channel_url.rstrip(channel_url.split('/')[-1])
                        lines = requests.get(channel_url, timeout=2).text.strip().split('\n')
                        ts_lists = [line.split('/')[-1] for line in lines if line.startswith('#') == False]
                        if ts_lists:
                            ts_url = channel_url_t + ts_lists[0]
                            with eventlet.Timeout(5, False):
                                start_time = time.time()
                                cont = requests.get(ts_url, timeout=6).content
                                resp_time = (time.time() - start_time) * 1                    
                            if cont and resp_time > 0:
                                temp_filename = f"temp_{hash(channel_url)}_{attempt}.ts"
                                with open(temp_filename, 'wb') as f:
                                    f.write(cont)
                                normalized_speed = len(cont) / resp_time / 1024 / 1024
                                os.remove(temp_filename)
                                
                                # 记录最佳速度
                                if normalized_speed > best_speed:
                                    best_speed = normalized_speed
                                
                                # 如果速度合格，直接通过
                                if normalized_speed > 0.001:
                                    break
                                else:
                                    print(f"第{attempt+1}次测速 {channel_name}: {normalized_speed:.3f} MB/s")
                            else:
                                print(f"第{attempt+1}次测速 {channel_name}: 获取内容失败")
                        else:
                            print(f"第{attempt+1}次测速 {channel_name}: 没有找到TS列表")
                    except Exception as e:
                        print(f"第{attempt+1}次测速 {channel_name} 失败: {str(e)}")
                
                # 根据最佳速度决定是否保留
                if best_speed > 0.001:
                    result = channel_name, channel_url, f"{best_speed:.3f}"
                    print(f"✓ {channel_name}, {channel_url}: {best_speed:.3f} MB/s (经过{max_retries}次测速)")
                    results.append(result)
                else:
                    print(f"× {channel_name}, {channel_url}: 经过{max_retries}次测速，最佳速度 {best_speed:.3f} MB/s，已过滤")
                
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

# 改进extract_channels函数，处理XML包装的JSON响应
def extract_channels(url):
    hotel_channels = []
    try:
        # 分割URL，获取协议和域名部分
        urls = url.split('/', 3)
        url_x = f"{urls[0]}//{urls[2]}"
        
        response = requests.get(url, timeout=3)
        response_text = response.text
        
        # 处理可能包含XML包装的JSON响应
        if "<?xml" in response_text and "{" in response_text:
            # 提取JSON部分
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                json_text = response_text[start_idx:end_idx]
                json_data = json.loads(json_text)
            else:
                return []
        else:
            json_data = response.json()
        
        # 处理不同的数据格式
        if "data" in json_data:
            for item in json_data.get('data', []):
                if isinstance(item, dict):
                    name = item.get('name', '')
                    urlx = item.get('url', '')
                    
                    # 统一处理频道名称
                    if name and urlx and ("tsfile" in urlx or "m3u8" in urlx or "hls" in urlx):
                        # 确保urlx以斜杠开头，避免双斜杠
                        if not urlx.startswith('/'):
                            urlx = '/' + urlx
                        urld = f"{url_x}{urlx}"
                        hotel_channels.append((name, urld))
                        print(f"解析到频道: {name} -> {urld}")
        
        return hotel_channels
    except Exception as e:
        print(f"解析频道错误 {url}: {e}")
        return []

# 修改统一频道名称函数，增加调试信息
def unify_channel_name(channels_list):
    new_channels_list = []
    matched_count = 0
    unmatched_count = 0
    
    for name, channel_url, speed in channels_list:
        original_name = name
        unified_name = None
        
        # 清理原始名称
        clean_name = remove_special_symbols(name.strip().lower())
        
        print(f"处理频道: {original_name} (清理后: {clean_name})")
        
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
                matched_count += 1
                print(f"数字匹配: '{original_name}' -> '{standard_name}'")
        
        # 如果没有通过数字匹配，再尝试映射表匹配
        if not unified_name:
            for standard_name, variants in CHANNEL_MAPPING.items():
                for variant in variants:
                    if exact_channel_match(name, variant):
                        unified_name = standard_name
                        matched_count += 1
                        break
                if unified_name:
                    break
        
        # 如果还是没有找到，保留原名称
        if not unified_name:
            unified_name = original_name
            unmatched_count += 1
            print(f"未匹配: '{original_name}' 保持原名称")
        
        new_channels_list.append(f"{unified_name},{channel_url},{speed}\n")
        if original_name != unified_name:
            print(f"频道名称统一: '{original_name}' -> '{unified_name}'")
    
    print(f"频道名称匹配统计: 已匹配 {matched_count} 个, 未匹配 {unmatched_count} 个")
    return new_channels_list
