# ফাইল: backend/apps/configuration/urls.py
# এই ফাইলটি configuration app-এর সব URL routes ধারণ করে।

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DistrictViewSet, UpazilaViewSet, ZoneViewSet, SubZoneViewSet,
    BoxViewSet, PackageViewSet, ConnectionTypeViewSet, ClientTypeViewSet,
    ProtocolTypeViewSet, BillingStatusViewSet,
)

router = DefaultRouter()
router.register('districts', DistrictViewSet, basename='districts')
router.register('upazilas', UpazilaViewSet, basename='upazilas')
router.register('zones', ZoneViewSet, basename='zones')
router.register('sub-zones', SubZoneViewSet, basename='sub-zones')
router.register('boxes', BoxViewSet, basename='boxes')
router.register('packages', PackageViewSet, basename='packages')
router.register('connection-types', ConnectionTypeViewSet, basename='connection-types')
router.register('client-types', ClientTypeViewSet, basename='client-types')
router.register('protocol-types', ProtocolTypeViewSet, basename='protocol-types')
router.register('billing-statuses', BillingStatusViewSet, basename='billing-statuses')

urlpatterns = [
    path('', include(router.urls)),
]
