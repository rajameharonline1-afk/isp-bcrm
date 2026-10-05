# ফাইল: backend/apps/hr/apps.py
# এই ফাইলটি hr app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class HrConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.hr'
    verbose_name = 'Hr'
