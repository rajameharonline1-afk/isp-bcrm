# ফাইল: backend/apps/income/apps.py
# এই ফাইলটি income app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class IncomeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.income'
    verbose_name = 'Income'
