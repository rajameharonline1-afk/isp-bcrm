# ফাইল: backend/apps/expense/urls.py
from rest_framework.routers import DefaultRouter
from .views import ExpenseCategoryViewSet, ExpenseViewSet

router = DefaultRouter()
router.register(r'categories', ExpenseCategoryViewSet, basename='expense-category')
router.register(r'',           ExpenseViewSet,         basename='expense')

urlpatterns = router.urls
