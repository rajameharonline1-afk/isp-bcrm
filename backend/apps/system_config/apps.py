# ফাইল: backend/apps/system_config/apps.py
# এই ফাইলটি system_config app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class SystemConfigConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.system_config'
    verbose_name = 'System Config'
