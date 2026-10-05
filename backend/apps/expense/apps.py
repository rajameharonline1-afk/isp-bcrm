# ফাইল: backend/apps/expense/apps.py
# এই ফাইলটি expense app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class ExpenseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.expense'
    verbose_name = 'Expense'
