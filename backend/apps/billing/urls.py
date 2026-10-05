# ফাইল: backend/apps/billing/urls.py
# এই ফাইলটি billing app-এর URL routes ধারণ করে।

from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
]
