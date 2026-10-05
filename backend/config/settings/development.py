# ফাইল: backend/config/settings/development.py
# এই ফাইলটি শুধুমাত্র Development পরিবেশের জন্য extra settings ধারণ করে।

from .base import *

# Development-এ Debug Mode চালু থাকবে
DEBUG = True

# Development-এ সব host অনুমোদিত
ALLOWED_HOSTS = ['*']

# Development-এ Email console-এ দেখাবে (আসল email পাঠাবে না)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Development Database (SQLite ব্যবহার করা যায় testing-এর জন্য)
# তবে PostgreSQL recommended
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

# Django Debug Toolbar (install করলে)
# INSTALLED_APPS += ['debug_toolbar']
# MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
# INTERNAL_IPS = ['127.0.0.1']

# Development-এ সব CORS origin অনুমোদিত
CORS_ALLOW_ALL_ORIGINS = True

# Development-এ REST Framework browsable API দেখাবে
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',  # Development-এ browser-friendly API
    ),
}

# Logs directory তৈরি না থাকলে error এড়ানোর জন্য
import os
os.makedirs(BASE_DIR / 'logs', exist_ok=True)
