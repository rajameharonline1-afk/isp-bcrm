# ফাইল: backend/apps/olt/urls.py
# এই ফাইলটি OLT module-এর সব HTTP API URL routes ধারণ করে।

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    OLTViewSet, OLTPortViewSet, ONUViewSet,
    ONUSignalLogListView, CriticalONUListView,
    OLTSNMPOIDProfileViewSet,
)

router = DefaultRouter()
router.register('devices', OLTViewSet, basename='olt-devices')
router.register('ports', OLTPortViewSet, basename='olt-ports')
router.register('onus', ONUViewSet, basename='onus')
router.register('snmp-profiles', OLTSNMPOIDProfileViewSet, basename='snmp-profiles')

urlpatterns = [
    path('', include(router.urls)),

    # Signal logs
    path('signal-logs/', ONUSignalLogListView.as_view(), name='onu-signal-logs'),

    # Critical ONUs (alert panel)
    path('critical-onus/', CriticalONUListView.as_view(), name='critical-onus'),
]
