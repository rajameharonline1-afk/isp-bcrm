# ফাইল: backend/apps/accounting/views.py
# Accounting module-এর সব API views।
# Chart of Accounts, Journal, Reports — সব এখানে।

import logging
from datetime import date
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.accounts.permissions import IsAdminOrStaff, IsAdminUser
from .models import AccountType, Account, JournalEntry, TransactionLine, AccountBalance
from .serializers import (
    AccountTypeSerializer, AccountSerializer, AccountCreateSerializer,
    JournalEntryListSerializer, JournalEntryDetailSerializer,
    JournalEntryCreateSerializer, AccountBalanceSerializer,
)
from .services import JournalService, ReportService

logger = logging.getLogger(__name__)


class AccountTypeViewSet(viewsets.ModelViewSet):
    """Account type পরিচালনা — Asset, Liability, Equity, Income, Expense।"""
    queryset           = AccountType.objects.all()
    serializer_class   = AccountTypeSerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]


class AccountViewSet(viewsets.ModelViewSet):
    """Chart of Accounts — সব account-এর list ও management।"""
    queryset = Account.objects.select_related('account_type', 'parent').order_by('code')
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields   = ['account_type', 'is_group', 'is_active', 'parent']
    search_fields      = ['code', 'name', 'description']
    ordering_fields    = ['code', 'name']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return AccountCreateSerializer
        return AccountSerializer

    def destroy(self, request, *args, **kwargs):
        account = self.get_object()
        if account.is_system:
            return Response({'error': 'System accounts cannot be deleted'}, status=400)
        if account.transaction_lines.exists():
            return Response({'error': 'Account has transactions — cannot delete'}, status=400)
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def chart(self, request):
        """
        Chart of Accounts tree structure।
        Account type অনুযায়ী grouped।
        """
        types = AccountType.objects.prefetch_related(
            'accounts__children',
        ).order_by('sort_order')

        result = []
        for at in types:
            top_accounts = Account.objects.filter(
                account_type=at, parent__isnull=True, is_active=True,
            ).order_by('code')
            result.append({
                'type':     at.name,
                'nature':   at.nature,
                'accounts': AccountSerializer(top_accounts, many=True).data,
            })
        return Response(result)

    @action(detail=True, methods=['get'])
    def ledger(self, request, pk=None):
        """একটি account-এর সব transactions (Ledger)।"""
        account     = self.get_object()
        from_date   = request.query_params.get('from_date')
        to_date     = request.query_params.get('to_date')
        from_d      = date.fromisoformat(from_date) if from_date else date(date.today().year, 1, 1)
        to_d        = date.fromisoformat(to_date) if to_date else date.today()

        lines = TransactionLine.objects.filter(
            account=account,
            journal__is_posted=True,
            journal__date__gte=from_d,
            journal__date__lte=to_d,
        ).select_related('journal').order_by('journal__date', 'journal__created_at')

        entries = []
        from django.db.models import Sum
        # Opening balance
        prev = TransactionLine.objects.filter(
            account=account, journal__is_posted=True, journal__date__lt=from_d,
        )
        opening = account.opening_balance + \
                  (prev.filter(type='debit').aggregate(t=Sum('amount'))['t'] or 0) - \
                  (prev.filter(type='credit').aggregate(t=Sum('amount'))['t'] or 0)

        running = opening
        for line in lines:
            if account.account_type.nature == 'debit':
                running += line.amount if line.type == 'debit' else -line.amount
            else:
                running += line.amount if line.type == 'credit' else -line.amount
            entries.append({
                'date':        str(line.journal.date),
                'entry_no':    line.journal.entry_no,
                'description': line.journal.description[:80],
                'debit':       float(line.amount) if line.type == 'debit' else None,
                'credit':      float(line.amount) if line.type == 'credit' else None,
                'balance':     float(running),
            })

        return Response({
            'account':         AccountSerializer(account).data,
            'from_date':       str(from_d),
            'to_date':         str(to_d),
            'opening_balance': float(opening),
            'closing_balance': float(running),
            'entries':         entries,
        })


class JournalEntryViewSet(viewsets.ModelViewSet):
    """Journal Entry পরিচালনা।"""
    queryset = JournalEntry.objects.prefetch_related('lines__account').order_by('-date', '-created_at')
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields   = ['entry_type', 'is_posted']
    search_fields      = ['entry_no', 'description', 'reference']
    ordering_fields    = ['date', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return JournalEntryListSerializer
        if self.action == 'create':
            return JournalEntryCreateSerializer
        return JournalEntryDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = JournalEntryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            journal = JournalService.create_journal(
                date_val=data['date'],
                description=data['description'],
                entry_type=data['entry_type'],
                reference=data.get('reference', ''),
                lines=data['lines'],
                created_by=request.user,
                auto_post=data.get('auto_post', False),
            )
        except (ValueError, Account.DoesNotExist) as e:
            return Response({'error': str(e)}, status=400)
        return Response(JournalEntryDetailSerializer(journal).data, status=201)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def post(self, request, pk=None):
        """Journal Entry post করা।"""
        journal = self.get_object()
        try:
            JournalService.post_journal(journal, posted_by=request.user)
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        return Response({'success': True, 'entry_no': journal.entry_no})

    def destroy(self, request, *args, **kwargs):
        journal = self.get_object()
        if journal.is_posted:
            return Response({'error': 'Posted journals cannot be deleted'}, status=400)
        return super().destroy(request, *args, **kwargs)


# =============================================
# Financial Report Views
# =============================================

class TrialBalanceView(APIView):
    """Trial Balance report।"""
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def get(self, request):
        from_date = request.query_params.get('from_date', str(date(date.today().year, 1, 1)))
        to_date   = request.query_params.get('to_date', str(date.today()))
        try:
            data = ReportService.get_trial_balance(
                date.fromisoformat(from_date),
                date.fromisoformat(to_date),
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        return Response({'from_date': from_date, 'to_date': to_date, 'accounts': data})


class ProfitLossView(APIView):
    """Profit & Loss Statement।"""
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def get(self, request):
        from_date = request.query_params.get('from_date', str(date(date.today().year, 1, 1)))
        to_date   = request.query_params.get('to_date', str(date.today()))
        try:
            data = ReportService.get_profit_loss(
                date.fromisoformat(from_date),
                date.fromisoformat(to_date),
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        return Response(data)


class CompareProfitLossView(APIView):
    """দুটি period-এর P&L তুলনা।"""
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def get(self, request):
        p = request.query_params
        try:
            data = ReportService.compare_profit_loss(
                date.fromisoformat(p.get('p1_from', str(date(date.today().year - 1, 1, 1)))),
                date.fromisoformat(p.get('p1_to',   str(date(date.today().year - 1, 12, 31)))),
                date.fromisoformat(p.get('p2_from', str(date(date.today().year, 1, 1)))),
                date.fromisoformat(p.get('p2_to',   str(date.today()))),
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        return Response(data)


class BalanceSheetView(APIView):
    """Balance Sheet — Assets = Liabilities + Equity।"""
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def get(self, request):
        as_of = request.query_params.get('as_of', str(date.today()))
        try:
            data = ReportService.get_balance_sheet(date.fromisoformat(as_of))
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        return Response(data)


class CashBookView(APIView):
    """Cash Book — Cash account-এর সব লেনদেন।"""
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def get(self, request):
        from_date = request.query_params.get('from_date', str(date.today()))
        to_date   = request.query_params.get('to_date', str(date.today()))
        try:
            data = ReportService.get_cash_book(
                date.fromisoformat(from_date),
                date.fromisoformat(to_date),
            )
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        return Response(data)


class AccountingDashboardView(APIView):
    """Accounting Dashboard — summary statistics।"""
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def get(self, request):
        from django.db.models import Sum, Q
        today = date.today()
        month_start = today.replace(day=1)

        from apps.income.models import Income
        from apps.expense.models import Expense
        from apps.billing.models import Payment

        data = {
            'today': {
                'income':  float(Income.objects.filter(date=today).aggregate(t=Sum('amount'))['t'] or 0),
                'expense': float(Expense.objects.filter(date=today).aggregate(t=Sum('amount'))['t'] or 0),
                'collection': float(Payment.objects.filter(payment_date=today).aggregate(t=Sum('amount'))['t'] or 0),
            },
            'this_month': {
                'income':  float(Income.objects.filter(date__gte=month_start).aggregate(t=Sum('amount'))['t'] or 0),
                'expense': float(Expense.objects.filter(date__gte=month_start).aggregate(t=Sum('amount'))['t'] or 0),
                'collection': float(Payment.objects.filter(payment_date__gte=month_start).aggregate(t=Sum('amount'))['t'] or 0),
            },
            'pending_journals': JournalEntry.objects.filter(is_posted=False).count(),
        }
        return Response(data)
