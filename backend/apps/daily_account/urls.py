# ফাইল: backend/apps/daily_account/urls.py
# এই ফাইলটি daily_account app-এর URL routes ধারণ করে।

from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
]
