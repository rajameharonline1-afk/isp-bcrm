# ফাইল: backend/apps/system_config/urls.py
# এই ফাইলটি System menu-র সব API URL route ধারণ করে।

from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    CompanySettingView, InvoiceSettingView, EmailSettingView, SystemSettingView,
    PaymentGatewayViewSet, PaymentProcessingFeeViewSet, AutomaticProcessViewSet,
    ActivityLoggerViewSet,
)

router = DefaultRouter()
router.register(r'payment-gateways',    PaymentGatewayViewSet,       basename='payment-gateway')
router.register(r'processing-fees',     PaymentProcessingFeeViewSet, basename='processing-fee')
router.register(r'automatic-process',   AutomaticProcessViewSet,     basename='automatic-process')
router.register(r'activity-loggers',    ActivityLoggerViewSet,       basename='activity-logger')

urlpatterns = [
    path('company/',  CompanySettingView.as_view(),  name='system-company'),
    path('invoice/',  InvoiceSettingView.as_view(),  name='system-invoice'),
    path('email/',    EmailSettingView.as_view(),    name='system-email'),
    path('settings/', SystemSettingView.as_view(),   name='system-settings'),
] + router.urls
