# ফাইল: backend/apps/income/urls.py
# এই ফাইলটি income app-এর URL routes ধারণ করে।

from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
]
