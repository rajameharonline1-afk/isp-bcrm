# ফাইল: backend/apps/purchase/apps.py
# এই ফাইলটি purchase app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class PurchaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.purchase'
    verbose_name = 'Purchase'
