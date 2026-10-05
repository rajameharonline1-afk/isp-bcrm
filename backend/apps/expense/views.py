# ফাইল: backend/apps/expense/views.py
from datetime import date
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Sum

from apps.accounts.permissions import IsAdminOrStaff
from .models import ExpenseCategory, Expense
from .serializers import ExpenseCategorySerializer, ExpenseListSerializer, ExpenseCreateSerializer


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    """Expense category পরিচালনা।"""
    queryset           = ExpenseCategory.objects.filter(is_active=True)
    serializer_class   = ExpenseCategorySerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]


class ExpenseViewSet(viewsets.ModelViewSet):
    """দৈনিক expense record পরিচালনা।"""
    queryset = Expense.objects.select_related('category', 'recorded_by').order_by('-date', '-created_at')
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields   = ['category', 'method', 'date']
    search_fields      = ['description', 'reference_no', 'payee']
    ordering_fields    = ['date', 'amount', 'created_at']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return ExpenseCreateSerializer
        return ExpenseListSerializer

    def perform_create(self, serializer):
        expense = serializer.save(recorded_by=self.request.user)
        from apps.accounting.services import JournalService
        journal = JournalService.post_expense_journal(expense, posted_by=self.request.user)
        if journal:
            expense.journal_entry = journal
            expense.save(update_fields=['journal_entry'])

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Expense summary।"""
        from_date = request.query_params.get('from_date', str(date.today()))
        to_date   = request.query_params.get('to_date', str(date.today()))
        qs = Expense.objects.filter(
            date__gte=date.fromisoformat(from_date),
            date__lte=date.fromisoformat(to_date),
        )
        data = qs.aggregate(total=Sum('amount'))
        data.update({
            'from_date': from_date, 'to_date': to_date,
            'by_category': list(
                qs.values('category__name').annotate(total=Sum('amount')).order_by('-total')
            ),
        })
        return Response(data)
