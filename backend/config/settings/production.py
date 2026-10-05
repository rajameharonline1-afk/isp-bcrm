# ফাইল: backend/config/settings/production.py
# এই ফাইলটি Production পরিবেশের জন্য সিকিউরিটি এবং performance settings ধারণ করে।

from .base import *

# Production-এ Debug অবশ্যই বন্ধ রাখতে হবে
DEBUG = False

# Production-এ নিরাপদ cookies
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_SSL_REDIRECT = True
X_FRAME_OPTIONS = 'DENY'

# HSTS (HTTP Strict Transport Security)
SECURE_HSTS_SECONDS = 31536000  # ১ বছর
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Production-এ Static Files (WhiteNoise বা Nginx দিয়ে serve করা হবে)
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# Production Logging
LOGGING['handlers']['file']['level'] = 'WARNING'
LOGGING['root']['level'] = 'WARNING'
