from django.urls import path
import views

urlpatterns = [
    path('process-ipa-dynamic/', views.process_ipa_dynamic, name='process-ipa-dynamic'),
    path('task-status/<str:task_id>/', views.task_status, name='task-status'),
    path('results/<str:task_id>/', views.get_results, name='get-results'),
]
