#coding=UTF-8
import os
import re
import json
import requests
import ipaddress  # 添加此模块用于判断内网地址
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_domain_new(domain):
    try:
        with open('res/config.json', 'r') as f:
            config = json.load(f)

        # 获取排除的域名列表
        exclude_domains = config.get('exclude_domains', {})
        if not isinstance(exclude_domains, dict):
            logging.error("配置文件中的 exclude_domains 应该是一个字典")
            return False

        for exclude_domain in exclude_domains.keys():
            if exclude_domain in domain:
                logging.info(f"排除域名: {domain}，匹配到排除列表: {exclude_domain}")
                return False
        return True
    except Exception as e:
        logging.error(f"检查域名时出错: {e}")
        return False

def check_domain_old(domain):
    try:
        with open('res/config_old.json', 'r') as f:
            config = json.load(f)

        # 获取排除的域名列表
        EXCLUDE_DOMAINS = config.get('exclude_domains', [])

        for exclude_domain in EXCLUDE_DOMAINS:
            if exclude_domain in domain:
                logging.info(f"排除域名: {domain}，匹配到排除列表: {exclude_domain}")
                return False
        return True
    except Exception as e:
        logging.error(f"检查域名时出错: {e}")
        return False
    
def check_domain_4_27(domain):
    try:
        with open('res/exclude_domains_4.27.json', 'r') as f:
            config = json.load(f)

        # 获取排除的域名列表
        EXCLUDE_DOMAINS = config.get('exclude_domains', [])

        for exclude_domain in EXCLUDE_DOMAINS:
            if exclude_domain in domain:
                logging.info(f"排除域名: {domain}，匹配到排除列表: {exclude_domain}")
                return False
        return True
    except Exception as e:
        logging.error(f"检查域名时出错: {e}")
        return False

def check_domain(domain):
    return check_domain_4_27(domain)  # 使用新的检查函数
    
def delete_repeated_data(data_list):
    """
    删除重复的数据，并记录最早的时间戳
    """
    logging.info("开始删除重复数据...")
    showed_domain_port = {}
    new_data_list = []
    for data in data_list:
        domain_name = data['domain_name']
        port = data['port']
        timestamp = data['timestamp']

        if domain_name not in showed_domain_port:
            showed_domain_port[domain_name] = {port: timestamp}
            new_data_list.append(data)
        elif port not in showed_domain_port[domain_name]:
            showed_domain_port[domain_name][port] = timestamp
            new_data_list.append(data)
        else:
            existing_timestamp = showed_domain_port[domain_name][port]
            if timestamp < existing_timestamp:
                showed_domain_port[domain_name][port] = timestamp
                for existing_data in new_data_list:
                    if existing_data['domain_name'] == domain_name and existing_data['port'] == port:
                        existing_data['timestamp'] = timestamp
                        break
    new_data_list.sort(key=lambda x: x['timestamp'])
    logging.info(f"去重后数据量: {len(new_data_list)}")
    return new_data_list

def query_ip_locations(data_list):
    """
    查询去重后的 IP 地址的位置信息，并更新到数据列表中
    """
    logging.info("开始查询 IP 位置信息...")
    ip_cache = {}
    for data in data_list:
        ip = data['IP']
        if ip not in ip_cache:
            ip_cache[ip] = query_ip_location(ip)
        data['ip_location'] = ip_cache[ip]
    logging.info("IP 位置信息查询完成")
    return data_list

def get_network_info_from_folder(folder_path):
    logging.info(f"开始处理文件夹: {folder_path}")
    data_list = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith('metadata.txt'):
                file_path = os.path.join(root, file)
                data = extract_data(root)
                if len(data):
                    data_list.append(data)
    logging.info(f"提取到的原始数据量: {len(data_list)}")
    unique_data = delete_repeated_data(data_list)
    return query_ip_locations(unique_data)

def extract_data(folder_path):
    logging.info(f"开始提取数据: {folder_path}")
    data = {}
    protocol = ''
    metadata_path = os.path.join(folder_path, 'metadata.txt')
    headers_path = os.path.join(folder_path, 'headers.txt')
    if not os.path.exists(metadata_path) or not os.path.exists(headers_path):
        logging.warning(f"缺少文件: {metadata_path if not os.path.exists(metadata_path) else headers_path}")
        return {}

    protocol = 'unknown'
    if os.path.exists(headers_path):
        with open(headers_path, 'r') as header:
            content_header = header.readline()
            if "tcp" in content_header:
                protocol = 'tcp'
            elif 'https' in content_header:
                protocol = 'https'
            elif 'http' in content_header:
                protocol = 'http'

    with open(metadata_path, 'r') as metadata:
        content_metadata = metadata.read()

        # 匹配时间戳
        timestamp_match = re.search(r"Timestamp:\t(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", content_metadata)
        if timestamp_match:
            data['timestamp'] = timestamp_match.group(1)
        else:
            logging.warning(f"未找到时间戳: {metadata_path}")

        # 匹配 Server Address 和 Resolved address
        matches = re.findall(r'Server Connection\nAddress:\s+(\S+)+:+(\S+)[^\n]*\nResolved address:\s+(\S+)', content_metadata)
        if not matches:
            logging.warning(f"未找到服务器连接信息: {metadata_path}")
        for match in matches:
            try:
                if not check_domain(match[0]):
                    logging.info(f"域名被排除: {match[0]}")
                    continue

                if ipaddress.ip_address(match[2]).is_private:
                    logging.info(f"跳过私有 IP: {match[2]}")
                    continue

                data.update({'domain_name': match[0], 'port': match[1], 'IP': match[2], 'protocol': protocol})
                return data
            except Exception as e:
                logging.error(f"处理匹配项时出错: {e}")
                continue

    return {}

def query_ip_location(ip):
    try:
        logging.info(f"查询 IP 位置信息: {ip}")
        response = requests.get(f'http://ip-api.com/json/{ip}', timeout=5)
        response.raise_for_status()
        data = response.json()

        if data['status'] == 'success':
            res = {
                'country': data.get('country'),
                'province': data.get('regionName'),
                'city': data.get('city'),
                'ISP': data.get('isp')
            }
            ret = f"国家/地区：{res['country']}，地区：{res['province']}，城市：{res['city']}，ISP：{res['ISP']}"
            return ret
        else:
            logging.warning(f"IP 查询失败: {ip}")
            return "查询ip信息失败或IP地址无效"

    except requests.Timeout:
        logging.error(f"查询 IP 超时: {ip}")
        return "查询ip信息超时"
    except requests.RequestException as e:
        logging.error(f"查询 IP 出错: {e}")
        return f"查询ip信息出错: {e}"
    
    
if __name__ == "__main__":
    folder_path = '/home/parzival/CERT/NetAnalyzer/results/network_origin_result/YoWhatsApp-202504231300-R59786485_1745570753_1745571699.apk'
    data_list = get_network_info_from_folder(folder_path)
    for data in data_list:
        print(data)