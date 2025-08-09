from django.http import JsonResponse
import download_utils
import wda_utils
import afterprocess
import llmds
import os
import json
import threading
import uuid
import shutil

# 全局锁和任务状态存储
process_lock = threading.Lock()
task_status_store = {}

# 视图函数

def process_ipa_task(url, task_id):
    """异步任务处理函数"""
    try:
        # 更新任务状态为开始
        task_status_store[task_id] = {'status': 'STARTED', 'result': None, 'error': None}
        
        # 调用下载函数
        app_id, country, bundle_id, app_name = download_utils.download_ipa_file(url)
        mitmproxydir = ""
        if country == 'cn':
            udid = '83c9e585007871c1daf44b09bca1292bb2453b81'
            mitmproxydir = "mitmproxydir/8080/log"
        elif country == 'us':
            udid = '176eefd47c0c777efb132dc3c307b9abbdbf1f8a'
            mitmproxydir = "mitmproxydir/8081/log"
        else:
            task_status_store[task_id] = {'status': 'FAILURE', 'result': None, 'error': 'Unsupported country code'}
            return

        if os.path.exists(mitmproxydir):
            shutil.rmtree(mitmproxydir)
        os.makedirs(mitmproxydir, exist_ok=True)

        # 安装和自动化测试
        wda_utils.dynamic_process(app_id, udid, bundle_id, country)

        # 提取抓包信息并生成json
        network_result = afterprocess.get_network_info_from_folder("mitmproxydir")

        # 使用LLM研判核心域名
        core_domains = []
        if network_result and 'all_domains' in network_result:
            all_domains = network_result['all_domains']
            if all_domains:
                try:
                    core_domains = llmds.filter_domains_need_to_block(app_name, bundle_id, all_domains)
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

        # 更新任务状态为成功
        task_status_store[task_id] = {'status': 'SUCCESS', 'result': final_result, 'error': None}

    except Exception as e:
        # 更新任务状态为失败
        task_status_store[task_id] = {'status': 'FAILURE', 'result': None, 'error': str(e)}
    finally:
        # 释放锁
        process_lock.release()

def process_ipa(request):
    url = request.GET.get('url')
    if not url:
        return JsonResponse({'error': 'URL is required'}, status=400)

    # 检查锁
    if not process_lock.acquire(blocking=False):
        return JsonResponse({'message': 'Device is currently analyzing, please wait.'}, status=429)

    # 生成唯一任务ID
    task_id = str(uuid.uuid4())
    
    # 初始化任务状态
    task_status_store[task_id] = {'status': 'PENDING', 'result': None, 'error': None}
    
    # 启动后台线程处理任务
    thread = threading.Thread(target=process_ipa_task, args=(url, task_id))
    thread.daemon = True
    thread.start()
    
    return JsonResponse({'message': 'IPA is being dynamically analyzed', 'task_id': task_id})

def task_status(request, task_id):
    if task_id not in task_status_store:
        return JsonResponse({'status': 'Task is pending or does not exist'}, status=404)
    
    task_info = task_status_store[task_id]
    status = task_info['status']
    
    if status == 'PENDING':
        return JsonResponse({'status': 'Task is pending'})
    elif status == 'STARTED':
        return JsonResponse({'status': 'Task is being analyzed'})
    elif status == 'SUCCESS':
        return JsonResponse({'status': 'Task completed', 'result': task_info['result']})
    elif status == 'FAILURE':
        return JsonResponse({'status': 'Task failed', 'error': task_info['error']}, status=500)
    else:
        return JsonResponse({'status': 'Task is in an unknown state'})
