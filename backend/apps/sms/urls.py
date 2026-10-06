# ফাইল: backend/apps/sms/urls.py
# এই ফাইলটি SMS Service-এর API URL route ধারণ করে।

from rest_framework.routers import DefaultRouter
from .views import SMSGatewayViewSet, SMSTemplateViewSet, SMSGroupViewSet, SMSMessageViewSet

router = DefaultRouter()
router.register(r'gateways',  SMSGatewayViewSet,  basename='sms-gateway')
router.register(r'templates', SMSTemplateViewSet, basename='sms-template')
router.register(r'groups',    SMSGroupViewSet,    basename='sms-group')
router.register(r'messages',  SMSMessageViewSet,  basename='sms-message')

urlpatterns = router.urls
