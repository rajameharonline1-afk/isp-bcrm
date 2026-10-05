# ফাইল: backend/apps/configuration/views.py
# এই ফাইলটি configuration module-এর সব API views ধারণ করে।

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema

from .models import District, Upazila, Zone, SubZone, Box, Package, ConnectionType, ClientType, ProtocolType, BillingStatus
from .serializers import (
    DistrictSerializer, UpazilaSerializer, ZoneSerializer, ZoneListSerializer,
    SubZoneSerializer, BoxSerializer, PackageSerializer, ConnectionTypeSerializer,
    ClientTypeSerializer, ProtocolTypeSerializer, BillingStatusSerializer,
)
from apps.accounts.permissions import IsAdminOrStaff, IsEmployeeOrAbove
from utils.pagination import StandardResultsSetPagination


@extend_schema(tags=['Configuration - District'])
class DistrictViewSet(viewsets.ModelViewSet):
    """জেলা তালিকা CRUD operations।"""
    queryset = District.objects.filter(is_active=True).order_by('name')
    serializer_class = DistrictSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name']

    def get_permissions(self):
        # শুধু Admin/Staff তৈরি, সম্পাদনা ও মুছতে পারবে; সবাই দেখতে পারবে
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminOrStaff()]
        return [IsAuthenticated()]


@extend_schema(tags=['Configuration - Zone'])
class ZoneViewSet(viewsets.ModelViewSet):
    """Zone management CRUD operations।"""
    queryset = Zone.objects.filter(is_active=True).order_by('name')
    permission_classes = [IsAuthenticated]
    search_fields = ['name']

    def get_serializer_class(self):
        if self.action == 'list':
            return ZoneListSerializer
        return ZoneSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminOrStaff()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        # Zone তৈরিকারীর তথ্য save করা
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def sub_zones(self, request, pk=None):
        """নির্দিষ্ট Zone-এর সব SubZone দেখানো।"""
        zone = self.get_object()
        sub_zones = zone.sub_zones.filter(is_active=True)
        serializer = SubZoneSerializer(sub_zones, many=True)
        return Response(serializer.data)


@extend_schema(tags=['Configuration - SubZone'])
class SubZoneViewSet(viewsets.ModelViewSet):
    """SubZone management CRUD operations।"""
    queryset = SubZone.objects.filter(is_active=True).select_related('zone').order_by('name')
    serializer_class = SubZoneSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['zone']
    search_fields = ['name']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminOrStaff()]
        return [IsAuthenticated()]


@extend_schema(tags=['Configuration - Box'])
class BoxViewSet(viewsets.ModelViewSet):
    """Box management CRUD operations।"""
    queryset = Box.objects.filter(is_active=True).select_related('sub_zone__zone').order_by('name')
    serializer_class = BoxSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['sub_zone', 'sub_zone__zone']
    search_fields = ['name', 'location']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminOrStaff()]
        return [IsAuthenticated()]


@extend_schema(tags=['Configuration - Package'])
class PackageViewSet(viewsets.ModelViewSet):
    """Internet Package CRUD operations।"""
    queryset = Package.objects.filter(is_active=True).order_by('monthly_price')
    serializer_class = PackageSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['package_type', 'is_active']
    search_fields = ['name', 'mikrotik_profile']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminOrStaff()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@extend_schema(tags=['Configuration - Lookup'])
class ConnectionTypeViewSet(viewsets.ModelViewSet):
    """Connection Type CRUD operations।"""
    queryset = ConnectionType.objects.filter(is_active=True)
    serializer_class = ConnectionTypeSerializer
    permission_classes = [IsAdminOrStaff]


@extend_schema(tags=['Configuration - Lookup'])
class ClientTypeViewSet(viewsets.ModelViewSet):
    """Client Type CRUD operations।"""
    queryset = ClientType.objects.filter(is_active=True)
    serializer_class = ClientTypeSerializer
    permission_classes = [IsAdminOrStaff]


@extend_schema(tags=['Configuration - Lookup'])
class ProtocolTypeViewSet(viewsets.ModelViewSet):
    """Protocol Type CRUD operations।"""
    queryset = ProtocolType.objects.filter(is_active=True)
    serializer_class = ProtocolTypeSerializer
    permission_classes = [IsAdminOrStaff]


@extend_schema(tags=['Configuration - Lookup'])
class BillingStatusViewSet(viewsets.ModelViewSet):
    """Billing Status CRUD operations।"""
    queryset = BillingStatus.objects.filter(is_active=True)
    serializer_class = BillingStatusSerializer
    permission_classes = [IsAdminOrStaff]


@extend_schema(tags=['Configuration - Upazila'])
class UpazilaViewSet(viewsets.ModelViewSet):
    """Upazila/Thana CRUD operations।"""
    queryset = Upazila.objects.filter(is_active=True).select_related('district').order_by('name')
    serializer_class = UpazilaSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['district']
    search_fields = ['name']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminOrStaff()]
        return [IsAuthenticated()]
