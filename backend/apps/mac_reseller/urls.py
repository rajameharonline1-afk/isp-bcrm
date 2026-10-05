# ফাইল: backend/apps/mac_reseller/urls.py
# এই ফাইলটি mac_reseller app-এর URL routes ধারণ করে।

from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
]
