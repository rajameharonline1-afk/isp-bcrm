# ফাইল: backend/apps/daily_account/apps.py
# এই ফাইলটি daily_account app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class DailyAccountConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.daily_account'
    verbose_name = 'Daily Account'
