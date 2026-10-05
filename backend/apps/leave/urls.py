# ফাইল: backend/apps/leave/urls.py
from rest_framework.routers import DefaultRouter
from .views import (
    LeaveCategoryViewSet, LeaveSetupViewSet,
    LeaveBalanceViewSet, LeaveApplicationViewSet,
)

router = DefaultRouter()
router.register(r'categories',   LeaveCategoryViewSet,    basename='leave-category')
router.register(r'setups',       LeaveSetupViewSet,       basename='leave-setup')
router.register(r'balances',     LeaveBalanceViewSet,     basename='leave-balance')
router.register(r'applications', LeaveApplicationViewSet, basename='leave-application')

urlpatterns = router.urls
