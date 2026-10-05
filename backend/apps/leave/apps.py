# ফাইল: backend/apps/leave/apps.py
# এই ফাইলটি leave app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class LeaveConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.leave'
    verbose_name = 'Leave'
