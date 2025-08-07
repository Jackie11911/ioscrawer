from celery import shared_task
from .download_utils import download_ipa_file
from .wda_utils import dynamic_process
from .afterprocess import get_network_info_from_folder
from .llmds import filter_domains_need_to_block
import os
import json

@shared_task
def process_ipa_task(url):
    try:
        # 调用下载函数
        app_id, country, bundle_id, app_name = download_ipa_file(url)
        if country == 'cn':
            udid = '83c9e585007871c1daf44b09bca1292bb2453b81'
        elif country == 'us':
            udid = '176eefd47c0c777efb132dc3c307b9abbdbf1f8a'
        else:
            return {'error': 'Unsupported country code'}

        # 安装和自动化测试
        dynamic_process(app_id, udid, bundle_id, country)

        # 提取抓包信息并生成json
        network_result = get_network_info_from_folder(f"out/{app_id}")

        # 使用LLM研判核心域名
        core_domains = []
        if network_result and 'all_domains' in network_result:
            all_domains = network_result['all_domains']
            if all_domains:
                try:
                    core_domains = filter_domains_need_to_block(app_name, bundle_id, all_domains)
                except Exception as e:
                    core_domains = []

        # 返回结果
        final_result = {
            'network_info': network_result,
            'core_domains': core_domains
        }

        # 确保 results 文件夹存在
        results_dir = "results"
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)

        # 将 final_result 写入 JSON 文件
        with open(os.path.join(results_dir, f"{app_id}.json"), "w", encoding="utf-8") as json_file:
            json.dump(final_result, json_file, ensure_ascii=False, indent=4)

        return final_result

    except Exception as e:
        return {'error': str(e)}
