# ফাইল: backend/apps/daily_account/views.py
# Daily Account — দৈনিক হিসাব বন্ধ করার API।

from datetime import date
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from apps.accounts.permissions import IsAdminOrStaff
from .models import DailyAccount
from .serializers import DailyAccountSerializer
from apps.accounting.services import DailyAccountService


class DailyAccountViewSet(viewsets.ReadOnlyModelViewSet):
    """দৈনিক হিসাব দেখানো ও closing।"""
    queryset = DailyAccount.objects.select_related('closed_by').order_by('-date')
    serializer_class   = DailyAccountSerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [DjangoFilterBackend, OrderingFilter]
    filterset_fields   = ['status']
    ordering_fields    = ['date']

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsAdminOrStaff])
    def close_today(self, request):
        """আজকের হিসাব বন্ধ করা।"""
        target_date = date.fromisoformat(
            request.data.get('date', str(date.today()))
        )
        try:
            daily = DailyAccountService.close_day(target_date, closed_by=request.user)
        except Exception as e:
            return Response({'error': str(e)}, status=400)
        return Response(DailyAccountSerializer(daily).data)

    @action(detail=False, methods=['get'])
    def today_summary(self, request):
        """আজকের income, expense, collection-এর live summary।"""
        from apps.income.models import Income
        from apps.expense.models import Expense
        from apps.billing.models import Payment
        from django.db.models import Sum, Q

        today = date.today()
        data  = {
            'date':       str(today),
            'income':     float(Income.objects.filter(date=today).aggregate(t=Sum('amount'))['t'] or 0),
            'expense':    float(Expense.objects.filter(date=today).aggregate(t=Sum('amount'))['t'] or 0),
            'collection': float(Payment.objects.filter(payment_date=today).aggregate(t=Sum('amount'))['t'] or 0),
            'by_method':  list(
                Payment.objects.filter(payment_date=today)
                .values('method').annotate(total=Sum('amount')).order_by('-total')
            ),
        }
        data['net'] = data['income'] + data['collection'] - data['expense']
        return Response(data)
