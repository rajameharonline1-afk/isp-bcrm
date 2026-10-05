# ফাইল: backend/apps/accounting/urls.py
from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    AccountTypeViewSet, AccountViewSet, JournalEntryViewSet,
    TrialBalanceView, ProfitLossView, CompareProfitLossView,
    BalanceSheetView, CashBookView, AccountingDashboardView,
)

router = DefaultRouter()
router.register(r'account-types', AccountTypeViewSet, basename='account-type')
router.register(r'accounts',      AccountViewSet,     basename='account')
router.register(r'journals',      JournalEntryViewSet, basename='journal')

urlpatterns = router.urls + [
    path('reports/trial-balance/',       TrialBalanceView.as_view(),       name='trial-balance'),
    path('reports/profit-loss/',         ProfitLossView.as_view(),         name='profit-loss'),
    path('reports/compare-profit-loss/', CompareProfitLossView.as_view(),  name='compare-profit-loss'),
    path('reports/balance-sheet/',       BalanceSheetView.as_view(),       name='balance-sheet'),
    path('reports/cash-book/',           CashBookView.as_view(),           name='cash-book'),
    path('dashboard/',                   AccountingDashboardView.as_view(), name='accounting-dashboard'),
]
