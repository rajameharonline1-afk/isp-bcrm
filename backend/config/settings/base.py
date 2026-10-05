# ফাইল: backend/config/settings/base.py
# এই ফাইলটি Django প্রজেক্টের সকল মূল settings কনফিগারেশন ধারণ করে।

import os
from pathlib import Path
from decouple import config
from datetime import timedelta

# প্রজেক্টের root directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Secret Key (Production-এ অবশ্যই পরিবর্তন করতে হবে)
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-this-in-production')

# Debug Mode
DEBUG = config('DEBUG', default=False, cast=bool)

# অনুমোদিত হোস্টগুলো
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

# Django Application Definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

# Third Party Apps (তৃতীয় পক্ষের অ্যাপসমূহ)
THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'channels',
    'drf_spectacular',
    'import_export',
    'django_celery_beat',
    'django_celery_results',
]

# ISP-BCRM প্রজেক্টের নিজস্ব অ্যাপসমূহ
LOCAL_APPS = [
    'apps.accounts',
    'apps.configuration',
    'apps.clients',
    'apps.billing',
    'apps.servers',
    'apps.hr',
    'apps.olt',
    'apps.network_diagram',
    'apps.leave',
    'apps.mac_reseller',
    'apps.support',
    'apps.tasks_management',
    'apps.bandwidth',
    'apps.purchase',
    'apps.inventory',
    'apps.assets',
    'apps.sales',
    'apps.income',
    'apps.expense',
    'apps.daily_account',
    'apps.accounting',
    'apps.reports',
    'apps.sms',
    'apps.system_config',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# Middleware কনফিগারেশন
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # CORS middleware (frontend-backend যোগাযোগের জন্য)
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

# Template কনফিগারেশন
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# WSGI এবং ASGI কনফিগারেশন
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# PostgreSQL ডেটাবেস কনফিগারেশন
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='isp_crm_db'),
        'USER': config('DB_USER', default='isp_crm_user'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'OPTIONS': {
            'connect_timeout': 10,
        },
    },
    # FreeRADIUS ডেটাবেস (আলাদা connection)
    'radius': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('RADIUS_DB_NAME', default='radius'),
        'USER': config('RADIUS_DB_USER', default='radius_user'),
        'PASSWORD': config('RADIUS_DB_PASSWORD', default=''),
        'HOST': config('RADIUS_DB_HOST', default='localhost'),
        'PORT': config('RADIUS_DB_PORT', default='5432'),
    },
}

# Password Validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Custom User Model (আমাদের নিজস্ব user model ব্যবহার করা হচ্ছে)
AUTH_USER_MODEL = 'accounts.User'

# Internationalization (বাংলাদেশ timezone)
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'
USE_I18N = True
USE_TZ = True

# Static & Media Files কনফিগারেশন
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static'
STATICFILES_DIRS = []

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default Primary Key Field Type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================
# Django REST Framework কনফিগারেশন
# =============================================
REST_FRAMEWORK = {
    # JWT Token authentication ব্যবহার করা হচ্ছে
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    # Pagination কনফিগারেশন (প্রতি পেজে ২০টি রেকর্ড)
    'DEFAULT_PAGINATION_CLASS': 'utils.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 20,
    # Filtering কনফিগারেশন
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    # API Documentation কনফিগারেশন
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # Error Renderer
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    # Throttling (Rate limiting)
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
    },
}

# =============================================
# JWT Token কনফিগারেশন
# =============================================
SIMPLE_JWT = {
    # Access token ৬০ মিনিট পর expire হবে
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=config('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', default=60, cast=int)),
    # Refresh token ৭ দিন পর expire হবে
    'REFRESH_TOKEN_LIFETIME': timedelta(days=config('JWT_REFRESH_TOKEN_LIFETIME_DAYS', default=7, cast=int)),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'TOKEN_OBTAIN_SERIALIZER': 'apps.accounts.serializers.CustomTokenObtainPairSerializer',
}

# =============================================
# Redis Cache কনফিগারেশন
# =============================================
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('CACHE_REDIS_URL', default='redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
        },
        'KEY_PREFIX': 'isp_crm',
        'TIMEOUT': 300,  # ৫ মিনিট cache expire
    }
}

# =============================================
# Celery কনফিগারেশন (Background Tasks)
# =============================================
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/2')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/3')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Dhaka'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# =============================================
# Django Channels কনফিগারেশন (WebSocket)
# =============================================
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [config('REDIS_URL', default='redis://localhost:6379/0')],
        },
    },
}

# =============================================
# CORS কনফিগারেশন (Frontend থেকে API access)
# =============================================
CORS_ALLOWED_ORIGINS = [
    config('FRONTEND_URL', default='http://localhost:3000'),
    'http://localhost:5173',  # Vite dev server
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# =============================================
# Email কনফিগারেশন
# =============================================
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('EMAIL_HOST_USER', default='noreply@ispcrm.com')

# =============================================
# SMS Gateway কনফিগারেশন
# =============================================
SMS_GATEWAY_URL = config('SMS_GATEWAY_URL', default='')
SMS_API_KEY = config('SMS_API_KEY', default='')
SMS_SENDER_ID = config('SMS_SENDER_ID', default='ISPCM')

# =============================================
# কোম্পানি তথ্য কনফিগারেশন
# =============================================
COMPANY_NAME = config('COMPANY_NAME', default='ISP Company')
COMPANY_EMAIL = config('COMPANY_EMAIL', default='')
COMPANY_PHONE = config('COMPANY_PHONE', default='')
COMPANY_ADDRESS = config('COMPANY_ADDRESS', default='')

# =============================================
# Payment Gateway (SSL Commerz)
# =============================================
SSLCOMMERZ_STORE_ID = config('SSLCOMMERZ_STORE_ID', default='')
SSLCOMMERZ_STORE_PASS = config('SSLCOMMERZ_STORE_PASS', default='')
SSLCOMMERZ_IS_SANDBOX = config('SSLCOMMERZ_IS_SANDBOX', default=True, cast=bool)

# =============================================
# API Documentation (Swagger/ReDoc)
# =============================================
SPECTACULAR_SETTINGS = {
    'TITLE': 'ISP-BCRM API',
    'DESCRIPTION': 'ISP Business & Network Management System REST API Documentation',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
}

# =============================================
# Logging কনফিগারেশন
# =============================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs/error.log',
        },
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
