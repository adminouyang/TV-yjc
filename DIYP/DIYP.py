urls = [
       #'https://dimaston.github.io/live.m3u',  #假m3u
       # 'https://ghproxy.cc/https://raw.githubusercontent.com/gaotianliuyun/gao/master/list.txt',   #暂时保留

        #'https://ghproxy.cc/https://raw.githubusercontent.com/ddhola/file/d7afb504b1ba4fef31813e1166cb892215a9c063/0609test',#港澳台、国外为主


       'https://ghproxy.cc/https://raw.githubusercontent.com/frxz751113/IPTVzb1/main/%E7%BB%BC%E5%90%88%E6%BA%90.txt',
       # #'https://raw.githubusercontent.com/ssili126/tv/main/itvlist.txt',
       # 'https://ghproxy.cc/https://raw.githubusercontent.com/Supprise0901/TVBox_live/main/live.txt',
	   #
       # 'https://ghproxy.cc/https://raw.githubusercontent.com/gaotianliuyun/gao/master/list.txt',
	   #


       # 'https://gitlab.com/p2v5/wangtv/-/raw/main/lunbo.txt',


       # 'https://ghproxy.cc/https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.txt',
       # 'https://ghproxy.cc/https://raw.githubusercontent.com/junge3333/juds6/main/yszb1.txt',

       # 'https://ghproxy.cc/https://raw.githubusercontent.com/kimwang1978/collect-tv-txt/main/others_output.txt',
       ''
]
# 合并文件的函数
def merge_txt_files(urls, output_filename='汇总.txt'):
    try:
        with open(output_filename, 'w', encoding='utf-8') as outfile:
            for url in urls:
                try:
                    response = requests.get(url)
                    response.raise_for_status()  # 确保请求成功
                    # 尝试将响应内容解码为UTF-8，如果失败则尝试其他编码
                    try:
                        content = response.content.decode('utf-8')
                    except UnicodeDecodeError:
                        content = response.content.decode('gbk')  # 尝试GBK编码
                    outfile.write(content + '\n')
                except requests.RequestException as e:
                    print(f'Error downloading {url}: {e}')
    except IOError as e:
        print(f'Error writing to file: {e}')

# 调用函数
merge_txt_files(urls)

#简体转繁体
# 创建一个OpenCC对象,指定转换的规则为繁体字转简体字
converter = OpenCC('t2s.json')#繁转简
#converter = OpenCC('s2t.json')#简转繁
# 打开txt文件
with open('汇总.txt', 'r', encoding='utf-8') as file:
    traditional_text = file.read()
# 进行繁体字转简体字的转换
simplified_text = converter.convert(traditional_text)
# 将转换后的简体字写入txt文件
with open('汇总.txt', 'w', encoding='utf-8') as file:
    file.write(simplified_text)

with open('汇总.txt', 'r', encoding="utf-8") as file:
    # 读取所有行并存储到列表中
    lines = file.readlines()
#定义替换规则的字典对频道名替换
replacements = {
    	"CCTV-1高清测试": "",
    	"CCTV-2高清测试": "",
    	"CCTV-7高清测试": "",
    	"CCTV-10高清测试": "",
    	"中央": "CCTV",
    	"高清""": "",
    	"HD": "",
    	"标清": "",
    	"amc": "AMC",
    	"CCTV1综合": "CCTV1",
    	"CCTV2财经": "CCTV2",
    	"CCTV3综艺": "CCTV3",
    	"国际": "",
    	"5体育": "5",
    	"6电影": "6",
    	"军农": "",
    	"8影视": "8",
    	"9纪录": "9",
    	"0科教": "0",
    	"2社会与法": "2",
    	"3新闻": "3",
    	"4少儿": "4",
    	"5音乐": "5",
    	"咪咕": "",
    	"超清": "",
    	"频道": "",
    	"CCTV-": "CCTV",
    	"CCTV_": "CCTV",
    	"CCTV风云剧场": "风云剧场",
    	"CCTV第一剧场": "第一剧场",
    	"CCTV怀旧剧场": "怀旧剧场",
    	"熊猫影院": "熊猫电影",
    	"熊猫爱生活": "熊猫生活",
    	"爱宠宠物": "宠物生活",
    	"[ipv6]": "",
    	"专区": "",
    	"卫视超": "卫视",
    	"CCTV风云剧场": "风云剧场",
    	"CCTV第一剧场": "第一剧场",
    	"CCTV怀旧剧场": "怀旧剧场",
    	"IPTV": "",
    	"PLUS": "+",
    	"＋": "+",
    	"(": "",
    	")": "",
    	"CAV": "",
    	"美洲": "",
    	"北美": "",
    	"12M": "",
    	"高清测试CCTV-1": "",
    	"高清测试CCTV-2": "",
    	"高清测试CCTV-7": "",
    	"高清测试CCTV-10": "",
    	"LD": "",
    	"HEVC20M": "",
    	"S,": ",",
    	"测试": "",
    	"CCTW": "CCTV",
    	"试看": "",
    	"测试": "",
    	" ": "",
    	"测试cctv": "CCTV",
    	"CCTV1综合": "CCTV1",
    	"CCTV2财经": "CCTV2",
    	"CCTV3综艺": "CCTV3",
    	"CCTV4国际": "CCTV4",
    	"CCTV4中文国际": "CCTV4",
    	"CCTV4欧洲": "CCTV4",
    	"CCTV5体育": "CCTV5",
    	"CCTV5+体育": "CCTV5+",
    	"CCTV6电影": "CCTV6",
    	"CCTV7军事": "CCTV7",
    	"CCTV7军农": "CCTV7",
    	"CCTV7农业": "CCTV7",
    	"CCTV7国防军事": "CCTV7",
    	"CCTV8电视剧": "CCTV8",
    	"CCTV8影视": "CCTV8",
    	"CCTV8纪录": "CCTV9",
    	"CCTV9记录": "CCTV9",
    	"CCTV9纪录": "CCTV9",
    	"CCTV10科教": "CCTV10",
    	"CCTV11戏曲": "CCTV11",
    	"CCTV12社会与法": "CCTV12",
    	"CCTV13新闻": "CCTV13",
    	"CCTV新闻": "CCTV13",
    	"CCTV14少儿": "CCTV14",
    	"央视14少儿": "CCTV14",
    	"CCTV少儿超": "CCTV14",
    	"CCTV15音乐": "CCTV15",
    	"CCTV音乐": "CCTV15",
    	"CCTV16奥林匹克": "CCTV16",
    	"CCTV17农业农村": "CCTV17",
    	"CCTV17军农": "CCTV17",
    	"CCTV17农业": "CCTV17",
    	"CCTV5+体育赛视": "CCTV5+",
    	"CCTV5+赛视": "CCTV5+",
    	"CCTV5+体育赛事": "CCTV5+",
    	"CCTV5+赛事": "CCTV5+",
    	"CCTV5+体育": "CCTV5+",
    	"CCTV5赛事": "CCTV5+",
    	"凤凰中文台": "凤凰中文",
    	"凤凰资讯台": "凤凰资讯",
    	"(CCTV4K测试）": "CCTV4K",
    	"上海东方卫视": "上海卫视",
    	"东方卫视": "上海卫视",
    	"内蒙卫视": "内蒙古卫视",
    	"福建东南卫视": "东南卫视",
    	"广东南方卫视": "南方卫视",
    	"湖南金鹰卡通": "金鹰卡通",
    	"炫动卡通": "哈哈炫动",
    	"卡酷卡通": "卡酷少儿",
    	"卡酷动画": "卡酷少儿",
    	"BRTVKAKU少儿": "卡酷少儿",
    	"优曼卡通": "优漫卡通",
    	"优曼卡通": "优漫卡通",
    	"嘉佳卡通": "佳嘉卡通",
    	"世界地理": "地理世界",
    	"CCTV世界地理": "地理世界",
    	"BTV北京卫视": "北京卫视",
    	"BTV冬奥纪实": "冬奥纪实",
    	"东奥纪实": "冬奥纪实",
    	"卫视台": "卫视",
    	"湖南电视台": "湖南卫视",
    	"少儿科教": "少儿",
    	"影视剧": "影视",
    	"电视剧": "影视",
    	"CCTV1CCTV1": "CCTV1",
    	"CCTV2CCTV2": "CCTV2",
    	"CCTV7CCTV7": "CCTV7",
    	"CCTV10CCTV10": "CCTV10"
}
with open('汇总.txt', 'w', encoding='utf-8') as new_file:
    for line in lines:
        # 去除行尾的换行符
        line = line.rstrip('\n')
        # 分割行，获取逗号前的字符串
        parts = line.split(',', 1)
        if len(parts) > 0:
            # 替换逗号前的字符串
            before_comma = parts[0]
            for old, new in replacements.items():
                before_comma = before_comma.replace(old, new)
            # 将替换后的逗号前部分和逗号后部分重新组合成一行，并写入新文件
            new_line = f'{before_comma},{parts[1]}\n' if len(parts) > 1 else f'{before_comma}\n'
            new_file.write(new_line)


# 打开文本文件进行读取
def read_and_process_file(input_filename, output_filename, encodings=['utf-8', 'gbk']):
    for encoding in encodings:
        try:
            with open(input_filename, 'r', encoding=encoding) as file:
                lines = file.readlines()
                break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"Cannot decode file '{input_filename}' with any of the provided encodings")

    with open(output_filename, 'w', encoding='utf-8') as outfile:
        for line in lines:
            if '$' in line:
                processed_line = line.split('$')[0].rstrip('\n')
                outfile.write(processed_line + '\n')
            else:
                outfile.write(line)

# 调用函数
read_and_process_file('汇总.txt', '汇总1.txt')  # 修改输出文件名以避免覆盖原始文件

###################################################################去重#####################################
def remove_duplicates(input_file, output_file):
    # 用于存储已经遇到的URL和包含genre的行
    seen_urls = set()
    seen_lines_with_genre = set()
    # 用于存储最终输出的行
    output_lines = []
    # 打开输入文件并读取所有行
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        print("去重前的行数：", len(lines))
        # 遍历每一行
        for line in lines:
            # 使用正则表达式查找URL和包含genre的行,默认最后一行
            urls = re.findall(r'[https]?[http]?[rtsp]?[rtmp]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', line)
            genre_line = re.search(r'\bgenre\b', line, re.IGNORECASE) is not None
            # 如果找到URL并且该URL尚未被记录
            if urls and urls[0] not in seen_urls:
                seen_urls.add(urls[0])
                output_lines.append(line)
            # 如果找到包含genre的行，无论是否已被记录，都写入新文件
            if genre_line:
                output_lines.append(line)
    # 将结果写入输出文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(output_lines)
    print("去重后的行数：", len(output_lines))
# 使用方法
remove_duplicates('汇总1.txt', '1.txt')

##########################
# with open('1.txt', 'r', encoding='utf-8') as file:
# 	# 从整理好的文本中按类别进行特定关键词提取
# 	keywords = ['PLTV','yinhe','TVOD','tsfile','itv','php','udp','ottrrs.hl.chinamobile.com','m3u8']  # 需要提取的关键字列表
# 	pattern = '|'.join(keywords)  # 创建正则表达式模式，匹配任意一个关键字
# # pattern = r"^(.*?),(?!#genre#)(.*?)$" #以分类直接复制
# with open('1.txt', 'r', encoding='utf-8') as file, open('2.txt', 'w', encoding='utf-8') as a:  #####定义临时文件名
# 	a.write('\n')  #####写入临时文件名
# 	for line in file:
# 		if 'genre'  and '2409:8087' not in line:
# 			if re.search(pattern, line):  # 如果行中有任意关键字
# 				a.write(line)  # 将该行写入输出文件
task_queue = Queue()
results = []
channels = []
error_channels = []
with open("1.txt", 'r', encoding='utf-8') as file:
	lines = file.readlines()
	for line in lines:
		line = line.strip()
		if line:
			channel_name, channel_url = line.split(',')
			channels.append((channel_name, channel_url))


# 定义工作线程函数
def worker():
	while True:
		# 从队列中获取一个任务
		channel_name, channel_url = task_queue.get()
		print(channel_url)
		try:
			channel_url_t = channel_url.rstrip(channel_url.split('/')[-1])  # m3u8链接前缀
			lines = requests.get(channel_url, timeout=1).text.strip().split('\n')  # 获取m3u8文件内容
			ts_lists = [line.split('/')[-1] for line in lines if line.startswith('#') == False]  # 获取m3u8文件下视频流后缀
			ts_lists_0 = ts_lists[0].rstrip(ts_lists[0].split('.ts')[-1])  # m3u8链接前缀
			ts_url = channel_url_t + ts_lists[0]  # 拼接单个视频片段下载链接

			# 多获取的视频数据进行5秒钟限制
			with eventlet.Timeout(6, False):
				start_time = time.time()
				content = requests.get(ts_url, timeout=1).content
				end_time = time.time()
				response_time = (end_time - start_time) * 1

			if content:
				with open(ts_lists_0, 'ab') as f:
					f.write(content)  # 写入文件
				file_size = len(content)
				#print(f"文件大小：{file_size} 字节")
				download_speed = file_size / response_time / 1024
				#print(f"下载速度：{download_speed:.3f} kB/s")
				normalized_speed = min(max(download_speed / 1024, 0.001), 100)  # 将速率从kB/s转换为MB/s并限制在1~100之间
				print(f"标准化后的速率：{normalized_speed:.3f} MB/s")
				# 删除下载的文件
				os.remove(ts_lists_0)
				result = channel_name, channel_url, f"{normalized_speed:.3f} MB/s"
				results.append(result)
				numberx = (len(results) + len(error_channels)) / len(channels) * 100
				print(
					f"可用频道：{len(results)} 个 , 不可用频道：{len(error_channels)} 个 , 总频道：{len(channels)} 个 ,总进度：{numberx:.2f} %。")
		except:
			error_channel = channel_name, channel_url
			error_channels.append(error_channel)
			numberx = (len(results) + len(error_channels)) / len(channels) * 100
			print(
				f"可用频道：{len(results)} 个 , 不可用频道：{len(error_channels)} 个 , 总频道：{len(channels)} 个 ,总进度：{numberx:.2f} %。")
		# 标记任务完成
		task_queue.task_done()


# 创建多个工作线程
num_threads = 5
for _ in range(num_threads):
	t = threading.Thread(target=worker, daemon=True)
	t.start()
# 添加下载任务到队列
for channel in channels:
	task_queue.put(channel)
# 等待所有任务完成
task_queue.join()


# 自定义排序函数，提取频道名称中的数字并按数字排序
def channel_key(channel_name):
	match = re.search(r'\d+', channel_name)
	if match:
		return int(match.group())
	else:
		return float('inf')  # 返回一个无穷大的数字作为关键字


# 对频道进行排序
results.sort(key=lambda x: (x[0], -float(x[2].split()[0])))
results.sort(key=lambda x: channel_key(x[0]))
now = datetime.now() #now = datetime.datetime.now()+ datetime.timedelta(hours=8)
current_time = now.strftime("%Y/%m/%d %H:%M")
# 生成iptv.txt文件
with open('2.txt', 'w', encoding='utf-8') as file:
	for result in results:
		channel_name, channel_url, speed = result
		file.write(f"{channel_name},{channel_url}\n")
#############
with open('2.txt', 'r', encoding='utf-8') as file:
	# 从整理好的文本中按类别进行特定关键词提取#############################################################################################
	keywords = ['CCTV', '风云剧场', '兵器', '女性', '地理', '央视文化', '风云音乐', '怀旧剧场', '第一剧场','CHC']  # 需要提取的关键字列表
	pattern = '|'.join(keywords)  # 创建正则表达式模式，匹配任意一个关键字
# pattern = r"^(.*?),(?!#genre#)(.*?)$" #以分类直接复制
with open('2.txt', 'r', encoding='utf-8') as file, open('央视.txt', 'w', encoding='utf-8') as a:  #####定义临时文件名
	a.write(f"央视频道{current_time}更新,#genre#\n")  #####写入临时文件名
	for line in file:
		if 'genre' not in line:
			if re.search(pattern, line):  # 如果行中有任意关键字
				a.write(line)  # 将该行写入输出文件

################
keywords = ['卫视','重温经典','']  # 需要提取的关键字列表
pattern = '|'.join(keywords)  # 创建正则表达式模式，匹配任意一个关键字
# pattern = r"^(.*?),(?!#genre#)(.*?)$" #以分类直接复制
with open('2.txt', 'r', encoding='utf-8') as file, open('卫视.txt', 'w', encoding='utf-8') as b:  #####定义临时文件名
	b.write('\n卫视频道,#genre#\n')  #####写入临时文件名
	for line in file:
		if 'genre' not in line:
			if re.search(pattern, line):  # 如果行中有任意关键字
				b.write(line)  # 将该行写入输出文件

################
keywords = ['1905','SiTV','NewTV','iHOT','梨园频道','睛彩','黑莓','超级','哒啵','金牌','精品','咪咕','爱情','潮妈辣婆','东北','动作电影',
	'古装剧场','海外剧场','欢乐剧场','家庭剧场','惊悚悬疑','军旅剧场','军事评论','明星大片','农业致富','武搏世界','炫舞未来','怡伴健康','中国功夫',
	'足球频道','纪实科教']  # 需要提取的关键字列表
pattern = '|'.join(keywords)  # 创建正则表达式模式，匹配任意一个关键字
# pattern = r"^(.*?),(?!#genre#)(.*?)$" #以分类直接复制
with open('2.txt', 'r', encoding='utf-8') as file, open('数字.txt', 'w', encoding='utf-8') as b:  #####定义临时文件名
	b.write('\n数字频道,#genre#\n')  #####写入临时文件名
	for line in file:
		if 'genre' not in line:
			if re.search(pattern, line):  # 如果行中有任意关键字
				b.write(line)  # 将该行写入输出文件

##############################
keywords = ['東森','华视','華視','中视','台视','民视','三立','中天','寰宇','MoMo','緯來','ELEVEN','豬哥亮','中天','非凡','AMC','amc','八大',
			'公視','靖天','靖洋','客家','采昌','TVBS','CATCHPLAY','好消息','龍華','龙华','博斯','亞洲','台湾','爱尔达','影迷数位','经典',
			'精选','电影原声台CMusic','MTV Live','History','大爱','电影免费看','番薯']  # 需要提取的关键字列表
pattern = '|'.join(keywords)  # 创建正则表达式模式，匹配任意一个关键字
# pattern = r"^(.*?),(?!#genre#)(.*?)$" #以分类直接复制
with open('2.txt', 'r', encoding='utf-8') as file, open('港奥台.txt', 'w', encoding='utf-8') as b:  #####定义临时文件名
	b.write('\n港奥台,#genre#\n')  #####写入临时文件名
	for line in file:
		if 'genre' not in line:
			if re.search(pattern, line):  # 如果行中有任意关键字
				b.write(line)  # 将该行写入输出文件

######################
keywords = ['安徽','合肥','肥西','蚌埠','滁州','池州','淮北','淮南','宿州','芜湖','六安','铜陵','安庆','宣城','马鞍山','阜阳','歙县','岳西','亳州','萧县','固镇','灵璧']  # 需要提取的关键字列表
pattern = '|'.join(keywords)  # 创建正则表达式模式，匹配任意一个关键字
# pattern = r"^(.*?),(?!#genre#)(.*?)$" #以分类直接复制
with open('2.txt', 'r', encoding='utf-8') as file, open('安徽.txt', 'w', encoding='utf-8') as b:  #####定义临时文件名
	b.write('\n安徽,#genre#\n')  #####写入临时文件名
	for line in file:
		if 'genre' not in line:
			if re.search(pattern, line):  # 如果行中有任意关键字
				b.write(line)  # 将该行写入输出文件

##########################
keywords = ['宝丰综合','泌阳新闻综合','郸城新闻综合','登封','邓州','方城','扶沟','巩义','固始','光山','滑县','潢川','济源','郏县','焦作','兰考',
			'梨园','临颍','灵宝','渑池','内黄','嵩县','唐河','卫辉','温县','淅川','西华','新安','新蔡','新县','新乡','新野','荥阳'
			'鄢陵','叶县','义马','宜阳','禹州','周口']  # 需要提取的关键字列表
pattern = '|'.join(keywords)  # 创建正则表达式模式，匹配任意一个关键字
# pattern = r"^(.*?),(?!#genre#)(.*?)$" #以分类直接复制
with open('2.txt', 'r', encoding='utf-8') as file, open('河南.txt', 'w', encoding='utf-8') as b:  #####定义临时文件名
	b.write('\n河南,#genre#\n')  #####写入临时文件名
	for line in file:
		if 'genre' not in line:
			if re.search(pattern, line):  # 如果行中有任意关键字
				b.write(line)  # 将该行写入输出文件
####################
keywords = ['湖北']  # 需要提取的关键字列表
pattern = '|'.join(keywords)  # 创建正则表达式模式，匹配任意一个关键字
# pattern = r"^(.*?),(?!#genre#)(.*?)$" #以分类直接复制
with open('2.txt', 'r', encoding='utf-8') as file, open('湖北.txt', 'w', encoding='utf-8') as b:  #####定义临时文件名
	b.write('\n湖北,#genre#\n')  #####写入临时文件名
	for line in file:
		if 'genre' not in line:
			if re.search(pattern, line):  # 如果行中有任意关键字
				b.write(line)  # 将该行写入输出文件
################
keywords = ['湖南','金鹰纪实','快乐垂钓','茶']  # 需要提取的关键字列表
pattern = '|'.join(keywords)  # 创建正则表达式模式，匹配任意一个关键字
# pattern = r"^(.*?),(?!#genre#)(.*?)$" #以分类直接复制
with open('2.txt', 'r', encoding='utf-8') as file, open('湖南.txt', 'w', encoding='utf-8') as b:  #####定义临时文件名
	b.write('\n湖南,#genre#\n')  #####写入临时文件名
	for line in file:
		if 'genre' not in line:
			if re.search(pattern, line):  # 如果行中有任意关键字
				b.write(line)  # 将该行写入输出文件

################
keywords = ['辽宁']  # 需要提取的关键字列表
pattern = '|'.join(keywords)  # 创建正则表达式模式，匹配任意一个关键字
# pattern = r"^(.*?),(?!#genre#)(.*?)$" #以分类直接复制
with open('2.txt', 'r', encoding='utf-8') as file, open('辽宁.txt', 'w', encoding='utf-8') as b:  #####定义临时文件名
	b.write('\n辽宁,#genre#\n')  #####写入临时文件名
	for line in file:
		if 'genre' not in line:
			if re.search(pattern, line):  # 如果行中有任意关键字
				b.write(line)  # 将该行写入输出文件

################
keywords = ['吉林']  # 需要提取的关键字列表
pattern = '|'.join(keywords)  # 创建正则表达式模式，匹配任意一个关键字
# pattern = r"^(.*?),(?!#genre#)(.*?)$" #以分类直接复制
with open('2.txt', 'r', encoding='utf-8') as file, open('吉林.txt', 'w', encoding='utf-8') as b:  #####定义临时文件名
	b.write('\n吉林,#genre#\n')  #####写入临时文件名
	for line in file:
		if 'genre' not in line:
			if re.search(pattern, line):  # 如果行中有任意关键字
				b.write(line)  # 将该行写入输出文件
##################
keywords = ['黑龙江','哈尔滨','大庆','齐齐哈尔','双鸭山']  # 需要提取的关键字列表
pattern = '|'.join(keywords)  # 创建正则表达式模式，匹配任意一个关键字
# pattern = r"^(.*?),(?!#genre#)(.*?)$" #以分类直接复制
with open('2.txt', 'r', encoding='utf-8') as file, open('黑龙江.txt', 'w', encoding='utf-8') as b:  #####定义临时文件名
	b.write('\n黑龙江,#genre#\n')  #####写入临时文件名
	for line in file:
		if 'genre' not in line:
			if re.search(pattern, line):  # 如果行中有任意关键字
				b.write(line)  # 将该行写入输出文件
################################
keywords = ['苍南','杭州余杭','金华东阳','金华兰溪','缙云','开化','兰溪','丽水','龙泉','龙游','宁波','平湖','普陀','钱江','青田','庆元',
			'衢州','上虞','绍兴','嵊州','松阳','遂昌','文成','温州','萧山','永嘉','云和','诸暨']  # 需要提取的关键字列表
pattern = '|'.join(keywords)  # 创建正则表达式模式，匹配任意一个关键字
# pattern = r"^(.*?),(?!#genre#)(.*?)$" #以分类直接复制
with open('3.txt', 'r', encoding='utf-8') as file, open('浙江.txt', 'w', encoding='utf-8') as b:  #####定义临时文件名
	b.write('\n浙江,#genre#\n')  #####写入临时文件名
	for line in file:
		if 'genre' not in line:
			if re.search(pattern, line):  # 如果行中有任意关键字
				b.write(line)  # 将该行写入输出文件

###########################

# 合并所有的txt文件
file_contents = []
file_paths = ["央视.txt", "卫视.txt","数字.txt","港奥台.txt","安徽.txt","河南.txt","湖南.txt","湖北.txt","辽宁.txt","吉林.txt","黑龙江.txt","浙江.txt"]  # 替换为实际的文件路径列表
for file_path in file_paths:
    with open(file_path, 'r', encoding="utf-8") as file:
        content = file.read()
        file_contents.append(content)

# 写入合并后的txt文件
with open("优质源.txt", "w", encoding="utf-8") as output:
    output.write('\n'.join(file_contents))
