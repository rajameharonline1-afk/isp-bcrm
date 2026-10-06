# ফাইল: backend/apps/mac_reseller/views.py
# এই ফাইলটি MAC Reseller মডিউলের সব API ViewSet ধারণ করে।

import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.accounts.permissions import IsAdminOrStaff, IsAdminUser
from .models import (
    MACReseller, MACResellerPackage, MACResellerTariffConfig,
    MACResellerFunding, ClientPGWPayment, PGWTransactionSettlement,
    MACResellerNotice,
)
from .serializers import (
    MACResellerListSerializer, MACResellerDetailSerializer, MACResellerCreateUpdateSerializer,
    MACResellerPackageSerializer,
    TariffConfigListSerializer, TariffConfigCreateUpdateSerializer,
    FundingListSerializer, FundingCreateSerializer, FundingApproveSerializer,
    ClientPGWPaymentListSerializer, ClientPGWPaymentDetailSerializer,
    PGWPaymentStatusUpdateSerializer,
    SettlementListSerializer, SettlementDetailSerializer, SettlementCreateSerializer,
    NoticeListSerializer, NoticeDetailSerializer,
)
from .filters import (
    MACResellerFilter, FundingFilter, PGWPaymentFilter,
    SettlementFilter, NoticeFilter,
)
from .services import MACResellerFundingService, PGWPaymentService, SettlementService

logger = logging.getLogger(__name__)


class MACResellerViewSet(viewsets.ModelViewSet):
    """
    MAC Reseller CRUD API।
    Admin/Staff: সব operation। Employee: শুধু read।
    """
    queryset = MACReseller.objects.prefetch_related('clients').order_by('name')
    permission_classes  = [IsAuthenticated, IsAdminOrStaff]
    filter_backends     = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class     = MACResellerFilter
    search_fields       = ['name', 'contact', 'email']
    ordering_fields     = ['name', 'balance', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return MACResellerListSerializer
        if self.action in ('create', 'update', 'partial_update'):
            return MACResellerCreateUpdateSerializer
        return MACResellerDetailSerializer

    def perform_create(self, serializer):
        # নতুন reseller তৈরিতে created_by সেট করা হয়
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def balance_history(self, request, pk=None):
        """নির্দিষ্ট Reseller-এর funding ইতিহাস।"""
        reseller = self.get_object()
        fundings = reseller.fundings.order_by('-funded_at')[:50]
        serializer = FundingListSerializer(fundings, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def clients(self, request, pk=None):
        """এই Reseller-এর অধীনে থাকা client তালিকা।"""
        from apps.clients.serializers import ClientListSerializer
        reseller = self.get_object()
        clients  = reseller.clients.filter(status='active').order_by('full_name')
        serializer = ClientListSerializer(clients, many=True)
        return Response(serializer.data)


class MACResellerPackageViewSet(viewsets.ModelViewSet):
    """
    MAC Reseller Package CRUD API।
    Admin: সব operation। Staff/Employee: read only।
    """
    queryset           = MACResellerPackage.objects.order_by('name')
    serializer_class   = MACResellerPackageSerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [SearchFilter, OrderingFilter]
    search_fields      = ['name']
    ordering_fields    = ['name', 'retail_price', 'bandwidth_down']

    def get_permissions(self):
        # শুধু Admin তৈরি ও মুছতে পারবে
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated(), IsAdminOrStaff()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class MACResellerTariffConfigViewSet(viewsets.ModelViewSet):
    """
    Reseller-ভিত্তিক Tariff Config API।
    Admin: সব operation। Staff: read only।
    """
    queryset = MACResellerTariffConfig.objects.select_related(
        'reseller', 'package', 'created_by'
    ).order_by('reseller__name', 'package__name')
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [DjangoFilterBackend, OrderingFilter]
    filterset_fields   = ['reseller', 'package', 'is_active']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return TariffConfigCreateUpdateSerializer
        return TariffConfigListSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated(), IsAdminOrStaff()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class MACResellerFundingViewSet(viewsets.ModelViewSet):
    """
    Reseller Account Funding API।
    Funding তৈরি, approve/reject করার endpoint।
    """
    queryset = MACResellerFunding.objects.select_related(
        'reseller', 'funded_by', 'approved_by'
    ).order_by('-funded_at')
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class    = FundingFilter
    search_fields      = ['reseller__name', 'transaction_id']
    ordering_fields    = ['funded_at', 'amount']
    http_method_names  = ['get', 'post', 'head', 'options']  # update/delete নেই

    def get_serializer_class(self):
        if self.action == 'create':
            return FundingCreateSerializer
        return FundingListSerializer

    def perform_create(self, serializer):
        # Funding request তৈরিতে funded_by সেট
        serializer.save(funded_by=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def approve(self, request, pk=None):
        """Funding request approve করে balance বাড়ানো।"""
        funding    = get_object_or_404(MACResellerFunding, pk=pk)
        serializer = FundingApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action_type = serializer.validated_data['action']
        try:
            if action_type == 'approve':
                updated = MACResellerFundingService.approve_funding(
                    funding_id=funding.pk, approved_by=request.user
                )
                return Response({'detail': f"{updated.amount}৳ balance যোগ হয়েছে।", 'balance': updated.balance_after})
            else:
                updated = MACResellerFundingService.reject_funding(
                    funding_id=funding.pk, rejected_by=request.user
                )
                return Response({'detail': "Funding request reject হয়েছে।"})
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ClientPGWPaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Client PGW Payment তালিকা ও বিস্তারিত API (read-only)।
    Payment status webhook update-এর জন্য আলাদা action।
    """
    queryset = ClientPGWPayment.objects.select_related(
        'client', 'reseller', 'billing'
    ).order_by('-created_at')
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class    = PGWPaymentFilter
    search_fields      = ['client__full_name', 'client__username', 'order_id', 'pgw_transaction_id']
    ordering_fields    = ['created_at', 'amount']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ClientPGWPaymentDetailSerializer
        return ClientPGWPaymentListSerializer

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def initiate(self, request):
        """
        নতুন PGW payment তৈরি করে Order ID ফেরত দেয়।
        Frontend এই order ID দিয়ে Gateway-এ redirect করবে।
        """
        from apps.clients.models import Client
        from apps.billing.models import Billing
        from decimal import Decimal

        client_id  = request.data.get('client_id')
        billing_id = request.data.get('billing_id')
        amount     = request.data.get('amount')
        gateway    = request.data.get('gateway', ClientPGWPayment.PaymentGateway.BKASH)

        if not all([client_id, amount, gateway]):
            return Response({'detail': 'client_id, amount এবং gateway আবশ্যক।'}, status=status.HTTP_400_BAD_REQUEST)

        client  = get_object_or_404(Client, pk=client_id)
        billing = get_object_or_404(Billing, pk=billing_id) if billing_id else None

        try:
            payment = PGWPaymentService.create_payment(
                client  = client,
                billing = billing,
                amount  = Decimal(str(amount)),
                gateway = gateway,
                reseller = client.mac_reseller,
            )
            return Response({'order_id': payment.order_id, 'payment_id': payment.pk}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error("PGW payment initiate error: %s", str(e))
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def callback(self, request):
        """
        Payment Gateway-এর callback/webhook গ্রহণ করে payment confirm করে।
        এই endpoint-টি payment success অথবা failure handle করে।
        """
        serializer = PGWPaymentStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            if data['status'] == ClientPGWPayment.PGWStatus.SUCCESS:
                payment = PGWPaymentService.confirm_payment(
                    order_id           = data['order_id'],
                    pgw_transaction_id = data['pgw_transaction_id'],
                    gateway_response   = data.get('gateway_response', {}),
                )
            else:
                payment = PGWPaymentService.fail_payment(
                    order_id = data['order_id'],
                    reason   = str(data.get('gateway_response', {})),
                )
            return Response({'detail': 'Payment status updated.', 'status': payment.status})
        except ClientPGWPayment.DoesNotExist:
            return Response({'detail': 'Payment not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error("PGW callback error: %s", str(e))
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PGWTransactionSettlementViewSet(viewsets.ModelViewSet):
    """
    PGW Transaction Settlement API।
    Settlement তৈরি ও সম্পন্ন করার endpoint।
    """
    queryset = PGWTransactionSettlement.objects.select_related(
        'reseller', 'settled_by'
    ).prefetch_related('payments').order_by('-settlement_date')
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [DjangoFilterBackend, OrderingFilter]
    filterset_class    = SettlementFilter
    ordering_fields    = ['settlement_date', 'net_settlement', 'created_at']
    http_method_names  = ['get', 'post', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return SettlementDetailSerializer
        if self.action == 'create':
            return SettlementCreateSerializer
        return SettlementListSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated(), IsAdminOrStaff()]

    def create(self, request, *args, **kwargs):
        """নতুন settlement তৈরি।"""
        serializer = SettlementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            settlement = SettlementService.create_settlement(
                reseller_id     = data['reseller_id'],
                payment_ids     = data['payment_ids'],
                settlement_date = data['settlement_date'],
                note            = data.get('note', ''),
                settled_by      = request.user,
            )
            return Response(
                SettlementListSerializer(settlement).data,
                status=status.HTTP_201_CREATED
            )
        except (MACReseller.DoesNotExist, ValueError) as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def complete(self, request, pk=None):
        """Settlement সম্পন্ন হিসেবে mark করা।"""
        try:
            settlement = SettlementService.complete_settlement(
                settlement_id = int(pk),
                settled_by    = request.user,
            )
            return Response({'detail': 'Settlement সম্পন্ন হয়েছে।', 'status': settlement.status})
        except PGWTransactionSettlement.DoesNotExist:
            return Response({'detail': 'Settlement পাওয়া যায়নি।'}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MACResellerNoticeViewSet(viewsets.ModelViewSet):
    """
    MAC Reseller Notice CRUD API।
    Admin: সব operation। Staff: read only।
    """
    queryset = MACResellerNotice.objects.prefetch_related(
        'target_resellers'
    ).order_by('-publish_at')
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class    = NoticeFilter
    search_fields      = ['title', 'content']
    ordering_fields    = ['publish_at', 'notice_type']

    def get_serializer_class(self):
        if self.action == 'list':
            return NoticeListSerializer
        return NoticeDetailSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated(), IsAdminOrStaff()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """বর্তমানে সক্রিয় এবং প্রকাশিত notice তালিকা।"""
        now = timezone.now()
        notices = self.get_queryset().filter(
            is_active=True,
            publish_at__lte=now,
        ).filter(
            # Expire না হওয়া notice (expire_at=null অথবা ভবিষ্যতে)
            expire_at__isnull=True
        ) | self.get_queryset().filter(
            is_active=True,
            publish_at__lte=now,
            expire_at__gt=now,
        )
        serializer = NoticeListSerializer(notices.distinct(), many=True)
        return Response(serializer.data)
