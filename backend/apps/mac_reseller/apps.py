# ফাইল: backend/apps/mac_reseller/apps.py
# এই ফাইলটি mac_reseller app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class MacResellerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.mac_reseller'
    verbose_name = 'Mac Reseller'
