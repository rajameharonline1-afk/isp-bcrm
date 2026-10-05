# ফাইল: backend/config/wsgi.py
# এই ফাইলটি Django প্রজেক্টের WSGI (traditional HTTP) entry point।

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

application = get_wsgi_application()
