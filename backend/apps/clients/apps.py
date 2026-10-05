# ফাইল: backend/apps/clients/apps.py
# এই ফাইলটি clients app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class ClientsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.clients'
    verbose_name = 'Clients'
