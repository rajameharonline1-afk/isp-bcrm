# ফাইল: backend/apps/accounting/apps.py
# এই ফাইলটি accounting app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class AccountingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounting'
    verbose_name = 'Accounting'
