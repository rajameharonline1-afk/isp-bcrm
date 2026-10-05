# ফাইল: backend/config/__init__.py
# Django startup-এ Celery app load করার জন্য।

from .celery import app as celery_app

__all__ = ('celery_app',)
