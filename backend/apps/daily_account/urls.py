# ফাইল: backend/apps/daily_account/urls.py
from rest_framework.routers import DefaultRouter
from .views import DailyAccountViewSet

router = DefaultRouter()
router.register(r'', DailyAccountViewSet, basename='daily-account')

urlpatterns = router.urls
