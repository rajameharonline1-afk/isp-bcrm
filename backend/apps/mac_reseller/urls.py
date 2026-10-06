# ফাইল: backend/apps/mac_reseller/urls.py
# এই ফাইলটি MAC Reseller মডিউলের সব API URL routes ধারণ করে।

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MACResellerViewSet,
    MACResellerPackageViewSet,
    MACResellerTariffConfigViewSet,
    MACResellerFundingViewSet,
    ClientPGWPaymentViewSet,
    PGWTransactionSettlementViewSet,
    MACResellerNoticeViewSet,
)

router = DefaultRouter()

# MAC Reseller list & detail
router.register(r'resellers',    MACResellerViewSet,              basename='mac-reseller')

# MAC Reseller Packages
router.register(r'packages',     MACResellerPackageViewSet,       basename='mac-reseller-package')

# Tariff Configuration
router.register(r'tariff-config', MACResellerTariffConfigViewSet, basename='tariff-config')

# Reseller Funding
router.register(r'funding',      MACResellerFundingViewSet,       basename='mac-reseller-funding')

# Client PGW Payments
router.register(r'pgw-payments', ClientPGWPaymentViewSet,         basename='client-pgw-payment')

# PGW Transaction Settlements
router.register(r'settlements',  PGWTransactionSettlementViewSet, basename='pgw-settlement')

# Reseller Notices
router.register(r'notices',      MACResellerNoticeViewSet,        basename='mac-reseller-notice')

urlpatterns = [
    path('', include(router.urls)),
]
