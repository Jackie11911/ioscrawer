from django.http import JsonResponse
from .download_utils import download_ipa_file
from .wda_utils import dynamic_process
from .afterprocess import get_network_info_from_folder
from .llmds import filter_domains_need_to_block
from .tasks import process_ipa_task
from celery.result import AsyncResult
import os
import json
import threading

# 全局锁
process_lock = threading.Lock()

# 视图函数

def process_ipa(request):
    url = request.GET.get('url')
    if not url:
        return JsonResponse({'error': 'URL is required'}, status=400)

    # 检查锁
    if not process_lock.acquire(blocking=False):
        return JsonResponse({'message': 'Device is currently analyzing, please wait.'}, status=429)

    try:
        # 调用异步任务
        task = process_ipa_task.delay(url)
        return JsonResponse({'message': 'IPA is being dynamically analyzed', 'task_id': task.id})
    finally:
        # 释放锁
        process_lock.release()

def task_status(request, task_id):
    result = AsyncResult(task_id)
    if result.state == 'PENDING':
        return JsonResponse({'status': 'Task is pending or does not exist'}, status=404)
    elif result.state == 'STARTED':
        return JsonResponse({'status': 'Task is being analyzed'})
    elif result.state == 'SUCCESS':
        return JsonResponse({'status': 'Task completed', 'result': result.result})
    elif result.state == 'FAILURE':
        return JsonResponse({'status': 'Task failed', 'error': str(result.info)}, status=500)
    else:
        return JsonResponse({'status': 'Task is in an unknown state'})
