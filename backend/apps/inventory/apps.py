# ফাইল: backend/apps/inventory/apps.py
# এই ফাইলটি inventory app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.inventory'
    verbose_name = 'Inventory'
