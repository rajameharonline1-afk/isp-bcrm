# ফাইল: backend/apps/configuration/apps.py
# এই ফাইলটি configuration app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class ConfigurationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.configuration'
    verbose_name = 'Configuration'
