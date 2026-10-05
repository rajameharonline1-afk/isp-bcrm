# ফাইল: backend/apps/network_diagram/apps.py
# এই ফাইলটি network_diagram app-এর Django AppConfig ধারণ করে।

from django.apps import AppConfig


class NetworkDiagramConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.network_diagram'
    verbose_name = 'Network Diagram'
