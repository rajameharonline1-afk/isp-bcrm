# ফাইল: backend/apps/sales/apps.py
# এই ফাইলটি sales app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class SalesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sales'
    verbose_name = 'Sales'
