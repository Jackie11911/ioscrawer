from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# 设置 Django 的默认设置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ioscrawer.settings')

app = Celery('ioscrawer')

# 使用 Django 的 settings 配置 Celery
app.config_from_object('django.conf:settings', namespace='CELERY')

# 自动发现任务
app.autodiscover_tasks()
