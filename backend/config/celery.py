# ফাইল: backend/config/celery.py
# এই ফাইলটি Celery background task queue কনফিগারেশন ধারণ করে।

import os
from celery import Celery
from django.conf import settings

# Django settings module set করা
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

app = Celery('isp_crm')

# Django settings থেকে Celery configuration নেওয়া (CELERY_ prefix সহ)
app.config_from_object('django.conf:settings', namespace='CELERY')

# সব apps থেকে tasks auto-discover করা
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


@app.task(bind=True)
def debug_task(self):
    """Celery connection test করার জন্য debug task।"""
    print(f'Request: {self.request!r}')
