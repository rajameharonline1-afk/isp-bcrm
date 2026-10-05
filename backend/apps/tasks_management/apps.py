# ফাইল: backend/apps/tasks_management/apps.py
# এই ফাইলটি tasks_management app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class TasksManagementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tasks_management'
    verbose_name = 'Tasks Management'
