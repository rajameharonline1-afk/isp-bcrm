# ফাইল: backend/apps/network_diagram/urls.py
# এই ফাইলটি network_diagram app-এর URL routes ধারণ করে।

from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
]
