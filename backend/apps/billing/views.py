# ফাইল: backend/apps/billing/views.py
# Billing ও Payment management-এর সব API views।

import logging
from decimal import Decimal
from datetime import date
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.shortcuts import get_object_or_404
from django.db.models import Sum

from apps.accounts.permissions import IsAdminOrStaff, IsEmployeeOrAbove
from .models import Billing, Payment
from .serializers import (
    BillingListSerializer, BillingDetailSerializer,
    PaymentListSerializer, PaymentCreateSerializer,
    BillGenerateSerializer,
)
from .filters import BillingFilter, PaymentFilter
from .services import BillingService

logger = logging.getLogger(__name__)


class BillingViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Billing records-এর read-only ViewSet।
    Bills generate ও payment collection custom action-এ।
    """
    queryset = Billing.objects.select_related(
        'client', 'generated_by',
    ).order_by('-bill_month', '-created_at')

    permission_classes = [IsAuthenticated, IsEmployeeOrAbove]
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class    = BillingFilter
    search_fields      = ['client__full_name', 'client__username', 'client__phone']
    ordering_fields    = ['bill_month', 'payable_amount', 'due_amount', 'created_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return BillingDetailSerializer
        return BillingListSerializer

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsAdminOrStaff])
    def generate(self, request):
        """Manual bill generation for a specific client & month।"""
        from apps.clients.models import Client
        serializer = BillGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        client     = get_object_or_404(Client, pk=serializer.validated_data['client_id'])
        bill_month = serializer.validated_data['bill_month'].replace(day=1)

        billing, created = BillingService.generate_bill_for_client(
            client=client, bill_month=bill_month, generated_by=request.user,
        )
        return Response(
            {
                'created':  created,
                'billing':  BillingDetailSerializer(billing).data,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsAdminOrStaff])
    def collect_payment(self, request):
        """Client-এর payment collect করা।"""
        from apps.clients.models import Client
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data       = serializer.validated_data
        client     = get_object_or_404(Client, pk=data['client_id'])
        billing    = None
        if data.get('billing_id'):
            billing = get_object_or_404(Billing, pk=data['billing_id'], client=client)

        amount = Decimal(str(data['amount']))

        # Advance balance থেকে payment করার option
        if data.get('use_advance') and client.advance_balance > 0:
            advance_apply = min(client.advance_balance, amount)
            BillingService.collect_payment(
                client=client, amount=advance_apply, method=Payment.PaymentMethod.ADVANCE,
                billing=billing, collected_by=request.user, note='From advance balance',
            )
            amount -= advance_apply

        result = {}
        if amount > 0:
            result = BillingService.collect_payment(
                client=client, amount=amount, method=data['method'],
                billing=billing, transaction_id=data.get('transaction_id', ''),
                collected_by=request.user, note=data.get('note', ''),
            )

        return Response(result)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Billing statistics — total due, total collected ইত্যাদি।"""
        month_param = request.query_params.get('month')
        qs = Billing.objects.all()

        if month_param:
            try:
                m = date.fromisoformat(month_param + '-01')
                qs = qs.filter(bill_month=m)
            except ValueError:
                pass

        data = qs.aggregate(
            total_billed    = Sum('payable_amount'),
            total_collected = Sum('paid_amount'),
            total_due       = Sum('due_amount'),
        )
        data.update({
            'unpaid_count': qs.filter(status=Billing.BillStatus.UNPAID).count(),
            'paid_count':   qs.filter(status=Billing.BillStatus.PAID).count(),
            'overdue_count': qs.filter(status=Billing.BillStatus.OVERDUE).count(),
        })
        return Response(data)


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """Payment records-এর read-only ViewSet।"""
    queryset = Payment.objects.select_related(
        'client', 'billing', 'collected_by',
    ).order_by('-created_at')

    permission_classes = [IsAuthenticated, IsEmployeeOrAbove]
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class    = PaymentFilter
    search_fields      = ['client__full_name', 'client__username', 'transaction_id']
    ordering_fields    = ['payment_date', 'amount', 'created_at']
    serializer_class   = PaymentListSerializer

    @action(detail=False, methods=['get'])
    def daily_collection(self, request):
        """আজকের সব payment-এর summary।"""
        today   = date.today()
        date_param = request.query_params.get('date', str(today))
        try:
            target = date.fromisoformat(date_param)
        except ValueError:
            target = today

        qs   = Payment.objects.filter(payment_date=target)
        data = qs.aggregate(total=Sum('amount'))
        data.update({
            'date':  str(target),
            'count': qs.count(),
            'by_method': list(
                qs.values('method').annotate(total=Sum('amount')).order_by('-total')
            ),
        })
        return Response(data)
