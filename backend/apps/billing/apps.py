# ফাইল: backend/apps/billing/apps.py
# এই ফাইলটি billing app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.billing'
    verbose_name = 'Billing'
