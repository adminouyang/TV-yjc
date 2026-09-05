#!/bin/bash
# checkout_ip.sh —— 纯 bash，放在 IP_Scan/ 目录下

BASE_DIR="checkout_ip"
RESULT_DIR="$BASE_DIR/result_ip_file"
mkdir -p "$RESULT_DIR"

# 交互选择城市
if [ $# -eq 0 ]; then
  echo "开始测试······"
  echo "在5秒内输入1~4可选择城市"
  echo "1.浙江电信"
  echo "2.江苏电信"
  echo "3.天津联通"
  echo "4.湖北电信"
  echo "5.河南电信"
  read -t 5 -p "超时未输入,将按默认设置测试" city_choice
  if [ -z "$city_choice" ]; then
      echo "未检测到输入,默认测试全部"
      city_choice=0
  fi
else
  city_choice=$1
fi

case $city_choice in
    1)  city="浙江电信";  stream="udp/233.50.201.100:5140" ;;
    2)  city="江苏电信";  stream="udp/239.49.8.19:9614" ;;
    5)  city="河北联通";  stream="rtp/239.253.92.154:6011" ;;
    3)  city="湖北电信";  stream="rtp/239.69.1.40:9880" ;;
    4)  city="河南电信";  stream="rtp/239.16.20.21:10210" ;;
    6)  city="广东电信";  stream="udp/239.77.1.152:5146" ;;
    7)  city="北京联通";  stream="rtp/239.3.1.241:8000" ;;
    8)  city="湖南电信";  stream="udp/239.76.246.151:1234" ;;
    9)  city="辽宁联通";  stream="rtp/232.0.0.126:1234" ;;
    10) city="四川电信";  stream="udp/239.93.0.169:5140" ;;
    11) city="山东电信";  stream="udp/239.21.1.87:5002" ;;
    12) city="陕西电信";  stream="rtp/239.111.205.35:5140" ;;
    13) city="广西电信";  stream="udp/239.81.0.107:4056" ;;
    14) city="贵州电信";  stream="rtp/238.255.2.1:5999" ;;
    15) city="山西联通";  stream="rtp/226.0.2.152:9128" ;;
    16) city="上海电信";  stream="udp/239.45.3.146:5140" ;;
    17) city="福建电信";  stream="rtp/239.61.2.132:8708" ;;
    18) city="江西电信";  stream="udp/239.252.220.63:5140" ;;
    19) city="安徽电信";  stream="rtp/238.1.79.27:4328" ;;
    20) city="天津联通";  stream="udp/225.1.1.111:5002" ;;
    21) city="宁夏电信";  stream="rtp/239.121.4.94:8538" ;;
    22) city="重庆电信";  stream="rtp/235.254.196.249:1268" ;;
    23) city="河北电信";  stream="rtp/239.254.200.174:6000" ;;
    24) city="河南联通";  stream="rtp/225.1.4.98:1127" ;;
    25) city="海南电信";  stream="rtp/239.253.64.253:5140" ;;
    26) city="黑龙江联通"; stream="rtp/229.58.190.150:5000" ;;
    27) city="甘肃电信";  stream="udp/239.255.30.249:8231" ;;
    28) city="新疆电信";  stream="udp/238.125.3.174:5140" ;;
    29) city="内蒙古电信"; stream="rtp/239.29.0.2:5000" ;;
    30) city="北京电信";  stream="rtp/225.1.8.21:8002" ;;
    31) city="湖北联通";  stream="rtp/228.0.0.60:6108" ;;
    32) city="吉林电信";  stream="rtp/239.37.0.231:5540" ;;
    33) city="云南电信";  stream="rtp/239.200.200.145:8840" ;;
    34) city="山东联通";  stream="rtp/239.253.254.78:8000" ;;
    35) city="重庆联通";  stream="udp/225.0.4.187:7980" ;;
    0)
        for option in {1..35}; do
          bash "$0" $option
        done
        exit 0
        ;;
esac

ipfile="$BASE_DIR/${city}_ip.txt"
result_file="$RESULT_DIR/${city}.txt"
good_ip="/tmp/good_${city}_$$.txt"
speed_good="/tmp/speed_good_${city}_$$.txt"

echo "======== 开始检索 ${city} ========"

if [ ! -f "$ipfile" ]; then
    echo "源文件 '$ipfile' 不存在，跳过 ${city}"
    exit 0
fi

# 去重
sort "$ipfile" | uniq | sed '/^\s*$/d' > "$ipfile.tmp" && mv "$ipfile.tmp" "$ipfile"

# 端口连通性检测
: > "$good_ip"
while IFS= read -r ip; do
    [ -z "$ip" ] && continue
    tmp_ip=$(echo -n "$ip" | sed 's/:/ /')
    output=$(nc -w 1 -v -z $tmp_ip 2>&1)
    if [[ $output == *"succeeded"* ]]; then
        echo "$ip" >> "$good_ip"
    fi
done < "$ipfile"

lines=$(wc -l < "$good_ip" | tr -d ' ')
echo "连接成功 $lines 个,开始测速······"

# 测速：只保留 > 800KB/s 的 IP
: > "$speed_good"
i=0
while IFS= read -r ip; do
    [ -z "$ip" ] && continue
    i=$((i + 1))
    url="http://$ip/$stream"
    speed=$(curl -o /dev/null -s -w '%{speed_download}' --connect-timeout 5 --max-time 40 "$url")
    if awk -v s="$speed" 'BEGIN{exit !(s+0 > 819200)}'; then
        echo "$ip" >> "$speed_good"
    fi
    speed_kb=$(awk -v s="$speed" 'BEGIN{printf "%.2f", s/1024}')
    echo "第$i/$lines个：$ip    速度: ${speed_kb} KB/s"
done < "$good_ip"

available_count=$(wc -l < "$speed_good" | tr -d ' ')

if [ "$available_count" -eq 0 ]; then
    echo "${city} 无可用IP，删除原文件 '$ipfile'"
    rm -f "$ipfile"
else
    echo "${city} 可用IP $available_count 个"
    if [ -f "$result_file" ]; then
        if diff <(sort -u "$speed_good") <(sort -u "$result_file") > /dev/null; then
            echo "${city} 结果与已有文件相同，不更新 '$result_file'"
            rm -f "$good_ip" "$speed_good"
            exit 0
        fi
    fi
    sort -u "$speed_good" > "$result_file"
    echo "${city} 结果已保存到 '$result_file'"
fi

rm -f "$good_ip" "$speed_good"
echo "${city} 测试完成"
