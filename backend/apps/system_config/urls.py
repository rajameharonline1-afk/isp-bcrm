# ফাইল: backend/apps/system_config/urls.py
# এই ফাইলটি system_config app-এর URL routes ধারণ করে।

from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
]
