# ফাইল: backend/apps/accounts/apps.py
# এই ফাইলটি accounts app-এর configuration ধারণ করে।

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    verbose_name = 'User Accounts'
