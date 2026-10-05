# ফাইল: backend/apps/olt/apps.py
from django.apps import AppConfig

class OltConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.olt'
    verbose_name = 'OLT Management'
