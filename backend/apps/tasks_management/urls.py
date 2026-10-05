# ফাইল: backend/apps/tasks_management/urls.py
# এই ফাইলটি tasks_management app-এর URL routes ধারণ করে।

from django.urls import path, include
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
]
