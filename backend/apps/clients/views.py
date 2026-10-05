# ফাইল: backend/apps/clients/views.py
# Client management-এর সব API views এখানে সংজ্ঞায়িত।
# CRUD + enable/disable/renew/change-package custom actions।

import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.shortcuts import get_object_or_404

from apps.accounts.permissions import IsAdminOrStaff, IsEmployeeOrAbove
from .models import Client, ClientStatusLog
from .serializers import (
    ClientListSerializer, ClientDetailSerializer,
    ClientCreateSerializer, ClientUpdateSerializer,
    ClientPasswordChangeSerializer, ClientRenewSerializer,
    ClientPackageChangeSerializer, ClientStatusLogSerializer,
)
from .filters import ClientFilter
from .services import ClientService

logger = logging.getLogger(__name__)


class ClientViewSet(viewsets.ModelViewSet):
    """
    Client management ViewSet।
    PPPoE client-এর সম্পূর্ণ CRUD ও network operation এখানে।
    """
    queryset = Client.objects.select_related(
        'zone', 'subzone', 'box', 'thana', 'district',
        'package', 'router', 'client_type', 'protocol', 'created_by',
    ).order_by('-created_at')

    permission_classes = [IsAuthenticated, IsEmployeeOrAbove]
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class    = ClientFilter
    search_fields      = ['full_name', 'username', 'phone', 'email', 'nid', 'address']
    ordering_fields    = ['created_at', 'full_name', 'expiry_date', 'monthly_bill', 'due_amount']

    def get_serializer_class(self):
        if self.action == 'list':
            return ClientListSerializer
        if self.action in ('create',):
            return ClientCreateSerializer
        if self.action in ('update', 'partial_update'):
            return ClientUpdateSerializer
        return ClientDetailSerializer

    def perform_create(self, serializer):
        # sync flags বের করে নেওয়া
        sync_mikrotik = serializer.validated_data.pop('sync_mikrotik', True)
        sync_radius   = serializer.validated_data.pop('sync_radius', True)

        client, sync_results = ClientService.create_client(
            validated_data=serializer.validated_data,
            created_by=self.request.user,
            sync_mikrotik=sync_mikrotik,
            sync_radius=sync_radius,
        )
        # Response-এ sync result সংযুক্ত করা
        self._last_sync_results = sync_results

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers  = self.get_success_headers(serializer.data)
        response = ClientDetailSerializer(
            Client.objects.get(username=serializer.validated_data['username'])
        ).data
        return Response(
            {'client': response, 'sync_results': getattr(self, '_last_sync_results', {})},
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    # =============================================
    # Custom Actions
    # =============================================

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminOrStaff])
    def enable(self, request, pk=None):
        """Client connection enable করা।"""
        client  = self.get_object()
        reason  = request.data.get('reason', 'Manual enable by staff')
        results = ClientService.enable_client(client, performed_by=request.user, reason=reason)
        return Response({'success': True, 'sync_results': results})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminOrStaff])
    def disable(self, request, pk=None):
        """Client connection disable করা।"""
        client  = self.get_object()
        reason  = request.data.get('reason', 'Suspended by staff')
        results = ClientService.disable_client(client, performed_by=request.user, reason=reason)
        return Response({'success': True, 'sync_results': results})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminOrStaff])
    def renew(self, request, pk=None):
        """Client connection renew করা।"""
        client     = self.get_object()
        serializer = ClientRenewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        results = ClientService.renew_client(
            client=client,
            months=serializer.validated_data['months'],
            performed_by=request.user,
            advance_used=serializer.validated_data.get('advance_used', 0),
        )
        return Response(results)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminOrStaff])
    def change_password(self, request, pk=None):
        """Client PPPoE password পরিবর্তন করা।"""
        client     = self.get_object()
        serializer = ClientPasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_password  = serializer.validated_data['new_password']
        sync_mikrotik = serializer.validated_data['sync_mikrotik']
        sync_radius   = serializer.validated_data['sync_radius']
        results       = {}

        # Mikrotik password আপডেট
        if sync_mikrotik and client.router:
            from apps.servers.services import MikrotikService, MikrotikAPIError
            try:
                svc = MikrotikService(**client.router.get_api_credentials())
                results['mikrotik'] = svc.change_pppoe_password(client.username, new_password)
            except MikrotikAPIError as e:
                results['mikrotik'] = {'success': False, 'error': str(e)}

        # RADIUS password আপডেট
        if sync_radius:
            from apps.servers.services import FreeRADIUSService, FreeRADIUSError
            try:
                results['radius'] = FreeRADIUSService.change_user_password(client.username, new_password)
            except FreeRADIUSError as e:
                results['radius'] = {'success': False, 'error': str(e)}

        # DB-তে save করা
        client.password = new_password
        client.save(update_fields=['password', 'updated_at'])

        return Response({'success': True, 'sync_results': results})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminOrStaff])
    def change_package(self, request, pk=None):
        """Client-এর package পরিবর্তন করা।"""
        from apps.configuration.models import Package
        client     = self.get_object()
        serializer = ClientPackageChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_package = get_object_or_404(Package, pk=serializer.validated_data['package_id'])
        results     = ClientService.change_package(client, new_package, performed_by=request.user)
        return Response({'success': True, 'sync_results': results})

    @action(detail=True, methods=['get'])
    def status_logs(self, request, pk=None):
        """Client-এর সব status change log দেখানো।"""
        client = self.get_object()
        logs   = ClientStatusLog.objects.filter(client=client).select_related('performed_by')
        serializer = ClientStatusLogSerializer(logs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def billing_history(self, request, pk=None):
        """Client-এর billing ও payment history।"""
        client = self.get_object()
        from apps.billing.models import Billing
        from apps.billing.serializers import BillingListSerializer
        bills = Billing.objects.filter(client=client).order_by('-bill_month')
        serializer = BillingListSerializer(bills, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """আগামী ৩ দিনে expire হওয়া client-দের তালিকা।"""
        from datetime import date, timedelta
        today    = date.today()
        deadline = today + timedelta(days=3)
        clients  = self.get_queryset().filter(
            status=Client.Status.ACTIVE,
            expiry_date__gte=today,
            expiry_date__lte=deadline,
        )
        serializer = ClientListSerializer(clients, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Client statistics — active, expired, due total ইত্যাদি।"""
        from django.db.models import Sum, Count
        qs = Client.objects.all()
        data = {
            'total':       qs.count(),
            'active':      qs.filter(status=Client.Status.ACTIVE).count(),
            'expired':     qs.filter(status=Client.Status.EXPIRED).count(),
            'suspended':   qs.filter(status=Client.Status.SUSPENDED).count(),
            'left':        qs.filter(status=Client.Status.LEFT).count(),
            'total_due':   qs.aggregate(t=Sum('due_amount'))['t'] or 0,
            'total_advance': qs.aggregate(t=Sum('advance_balance'))['t'] or 0,
        }
        return Response(data)
