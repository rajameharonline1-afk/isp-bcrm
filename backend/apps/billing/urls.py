# ফাইল: backend/apps/billing/urls.py
from rest_framework.routers import DefaultRouter
from .views import BillingViewSet, PaymentViewSet

router = DefaultRouter()
router.register(r'billings', BillingViewSet, basename='billing')
router.register(r'payments', PaymentViewSet, basename='payment')

urlpatterns = router.urls
