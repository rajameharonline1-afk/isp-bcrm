# ফাইল: backend/apps/assets/apps.py
# এই ফাইলটি assets app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class AssetsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.assets'
    verbose_name = 'Assets'
