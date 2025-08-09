from django.urls import path
import views

urlpatterns = [
    path('process-ipa/', views.process_ipa, name='process-ipa'),
    path('task-status/<str:task_id>/', views.task_status, name='task-status'),
]
