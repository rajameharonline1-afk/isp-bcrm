# ফাইল: backend/apps/income/views.py
from datetime import date
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Sum

from apps.accounts.permissions import IsAdminOrStaff
from .models import IncomeCategory, Income
from .serializers import IncomeCategorySerializer, IncomeListSerializer, IncomeCreateSerializer


class IncomeCategoryViewSet(viewsets.ModelViewSet):
    """Income category পরিচালনা।"""
    queryset           = IncomeCategory.objects.filter(is_active=True)
    serializer_class   = IncomeCategorySerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]


class IncomeViewSet(viewsets.ModelViewSet):
    """দৈনিক income record পরিচালনা।"""
    queryset = Income.objects.select_related('category', 'client', 'collected_by').order_by('-date', '-created_at')
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields   = ['category', 'method', 'date', 'client']
    search_fields      = ['description', 'reference_no']
    ordering_fields    = ['date', 'amount', 'created_at']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return IncomeCreateSerializer
        return IncomeListSerializer

    def perform_create(self, serializer):
        income = serializer.save(collected_by=self.request.user)
        # Auto journal entry তৈরি করা
        from apps.accounting.services import JournalService
        journal = JournalService.post_income_journal(income, posted_by=self.request.user)
        if journal:
            income.journal_entry = journal
            income.save(update_fields=['journal_entry'])

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Income summary — date range অনুযায়ী।"""
        from_date = request.query_params.get('from_date', str(date.today()))
        to_date   = request.query_params.get('to_date', str(date.today()))
        qs = Income.objects.filter(
            date__gte=date.fromisoformat(from_date),
            date__lte=date.fromisoformat(to_date),
        )
        data = qs.aggregate(total=Sum('amount'))
        data.update({
            'from_date': from_date, 'to_date': to_date,
            'by_category': list(
                qs.values('category__name').annotate(total=Sum('amount')).order_by('-total')
            ),
            'by_method': list(
                qs.values('method').annotate(total=Sum('amount')).order_by('-total')
            ),
        })
        return Response(data)
