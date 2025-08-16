from django.urls import path
import views

urlpatterns = [
    path('process-ipa-dynamic/', views.process_ipa_dynamic, name='process-ipa-dynamic'),
    path('task-status/<str:task_id>/', views.task_status, name='task-status'),
]
