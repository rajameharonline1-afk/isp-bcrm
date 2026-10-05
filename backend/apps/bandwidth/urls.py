# ফাইল: backend/apps/bandwidth/urls.py
# এই ফাইলটি bandwidth app-এর URL routes ধারণ করে।

from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
]
