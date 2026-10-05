# ফাইল: backend/apps/olt/apps.py
# এই ফাইলটি olt app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class OltConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.olt'
    verbose_name = 'Olt'
