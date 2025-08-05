from django.urls import path
from . import views

urlpatterns = [
    path('process-ipa/', views.process_ipa, name='process_ipa'),
    path('task-status/<str:task_id>/', views.task_status, name='task_status'),
]
