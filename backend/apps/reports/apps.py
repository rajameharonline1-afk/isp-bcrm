# ফাইল: backend/apps/reports/apps.py
# এই ফাইলটি reports app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class ReportsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.reports'
    verbose_name = 'Reports'
