# ফাইল: backend/apps/support/apps.py
# এই ফাইলটি support app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class SupportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.support'
    verbose_name = 'Support'
