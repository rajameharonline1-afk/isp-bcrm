# ফাইল: backend/apps/sms/apps.py
# এই ফাইলটি sms app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class SmsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sms'
    verbose_name = 'Sms'
