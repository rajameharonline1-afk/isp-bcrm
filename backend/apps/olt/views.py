# ফাইল: backend/apps/olt/views.py
# এই ফাইলটি OLT management, ONU monitoring এবং signal data-এর সব API views ধারণ করে।

from django.utils import timezone
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from .models import OLT, OLTPort, ONU, ONUSignalLog, ONUEvent, OLTSNMPOIDProfile
from .serializers import (
    OLTSerializer, OLTListSerializer, OLTPortSerializer,
    ONUSerializer, ONUListSerializer, ONUSignalLogSerializer,
    ONUEventSerializer, OLTSNMPOIDProfileSerializer,
    ONUAuthorizeSerializer, ONUDeleteSerializer, ONUAddManualSerializer,
)
from .services import OLTService, SNMPService
from apps.accounts.permissions import IsAdminOrStaff, IsAdminUser
from utils.pagination import StandardResultsSetPagination, LargeResultsSetPagination


@extend_schema(tags=['OLT - Devices'])
class OLTViewSet(viewsets.ModelViewSet):
    """OLT device CRUD ও management operations।"""
    queryset = OLT.objects.filter(is_active=True).select_related('zone')
    permission_classes = [IsAdminOrStaff]
    filterset_fields = ['status', 'vendor', 'zone', 'is_active']
    search_fields = ['name', 'ip_address', 'model']

    def get_serializer_class(self):
        if self.action == 'list':
            return OLTListSerializer
        return OLTSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='test-snmp')
    def test_snmp(self, request, pk=None):
        """OLT-এ SNMP connection test করা।"""
        olt = self.get_object()
        try:
            snmp = OLTService.get_snmp_service(olt)
            result = snmp.test_connection()

            # Status আপডেট
            olt.status = 'online' if result['success'] else 'offline'
            olt.save(update_fields=['status'])

            return Response(result)
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='poll-now')
    def poll_now(self, request, pk=None):
        """Manual SNMP poll শুরু করা (Celery task queue-তে)।"""
        olt = self.get_object()
        from .tasks import poll_olt_snmp
        task = poll_olt_snmp.delay(olt.id)
        return Response({
            'message': f'{olt.name}-এর জন্য SNMP poll শুরু হয়েছে।',
            'task_id': task.id,
        })

    @action(detail=True, methods=['get'], url_path='summary')
    def summary(self, request, pk=None):
        """OLT-এর সব ONU statistics summary।"""
        olt = self.get_object()
        from django.db.models import Count, Avg, Min, Max

        stats = ONU.objects.filter(olt=olt).aggregate(
            total=Count('id'),
            online=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(status='online')),
            offline=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(status='offline')),
            unauthorized=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(status='unauthorized')),
            avg_rx=Avg('rx_power'),
            min_rx=Min('rx_power'),
            max_rx=Max('rx_power'),
        )

        from django.db.models import Q
        critical_count = ONU.objects.filter(
            olt=olt, status='online', rx_power__isnull=False
        ).filter(rx_power__lt=-27.0).count()

        return Response({
            'olt': {'id': olt.id, 'name': olt.name, 'status': olt.status},
            'onu_stats': stats,
            'critical_signal_count': critical_count,
            'last_polled': olt.last_polled,
        })

    @action(detail=True, methods=['get'], url_path='ports')
    def ports(self, request, pk=None):
        """OLT-এর সব PON port list।"""
        olt = self.get_object()
        ports = OLTPort.objects.filter(olt=olt, is_active=True).order_by('frame', 'slot', 'port')
        serializer = OLTPortSerializer(ports, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='sync-ports')
    def sync_ports(self, request, pk=None):
        """SSH CLI দিয়ে OLT থেকে port information sync করা।"""
        olt = self.get_object()
        # TODO: SSH দিয়ে port discovery implement করা
        return Response({'message': 'Port sync feature coming soon.'})


@extend_schema(tags=['OLT - Ports'])
class OLTPortViewSet(viewsets.ModelViewSet):
    """OLT Port CRUD operations।"""
    queryset = OLTPort.objects.filter(is_active=True).select_related('olt')
    serializer_class = OLTPortSerializer
    permission_classes = [IsAdminOrStaff]
    filterset_fields = ['olt', 'port_type', 'is_active']


@extend_schema(tags=['OLT - ONUs'])
class ONUViewSet(viewsets.ModelViewSet):
    """ONU inventory এবং management operations।"""
    permission_classes = [IsAdminOrStaff]
    pagination_class = LargeResultsSetPagination
    filterset_fields = ['olt', 'port', 'status', 'pending_action']
    search_fields = ['serial_number', 'mac_address', 'description', 'pppoe_username']

    def get_queryset(self):
        return ONU.objects.select_related(
            'olt', 'port', 'client'
        ).order_by('olt', 'port__frame', 'port__slot', 'port__port', 'onu_id')

    def get_serializer_class(self):
        if self.action == 'list':
            return ONUListSerializer
        return ONUSerializer

    @action(detail=False, methods=['post'], url_path='authorize')
    def authorize_onu(self, request):
        """
        ONU authorize করা (Celery task-এ SSH CLI দিয়ে)।
        Status pending_auth → SSH command → authorized বা failed।
        WebSocket দিয়ে React-এ real-time status update।
        """
        serializer = ONUAuthorizeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Celery task queue করা
        from .tasks import authorize_onu_task
        task = authorize_onu_task.delay(
            onu_id=data['onu_id'],
            user_id=request.user.id,
            lineprofile_id=data.get('lineprofile_id', 10),
            srvprofile_id=data.get('srvprofile_id', 10),
            profile_name=data.get('profile_name', 'FTTH'),
            desc=data.get('desc', ''),
        )

        return Response({
            'message': 'ONU authorize task শুরু হয়েছে। WebSocket-এ status আপডেট পাবেন।',
            'task_id': task.id,
        }, status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=['post'], url_path='delete-onu')
    def delete_onu(self, request):
        """ONU delete করা (Celery task-এ SSH CLI দিয়ে)।"""
        serializer = ONUDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from .tasks import delete_onu_task
        task = delete_onu_task.delay(
            onu_id=serializer.validated_data['onu_id'],
            user_id=request.user.id,
        )
        return Response({
            'message': 'ONU delete task শুরু হয়েছে।',
            'task_id': task.id,
        }, status=status.HTTP_202_ACCEPTED)

    @action(detail=False, methods=['post'], url_path='add-manual')
    def add_manual(self, request):
        """Manual ONU যোগ করা (SNMP discover ছাড়া)।"""
        serializer = ONUAddManualSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            olt  = OLT.objects.get(id=data['olt_id'])
            port = OLTPort.objects.get(id=data['port_id'])
        except (OLT.DoesNotExist, OLTPort.DoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

        onu, created = ONU.objects.get_or_create(
            olt=olt, port=port, onu_id=data['onu_id'],
            defaults={
                'serial_number': data['serial_number'],
                'description':   data.get('description', ''),
                'client_id':     data.get('client_id'),
                'status':        ONU.ONUStatus.UNAUTHORIZED,
            }
        )
        return Response(ONUSerializer(onu).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=True, methods=['patch'], url_path='map-client')
    def map_client(self, request, pk=None):
        """ONU-র সাথে client mapping করা।"""
        onu = self.get_object()
        client_id = request.data.get('client_id')
        onu.client_id = client_id
        onu.save(update_fields=['client'])
        return Response({'success': True, 'message': 'Client mapping আপডেট হয়েছে।'})

    @action(detail=True, methods=['get'], url_path='signal-history')
    def signal_history(self, request, pk=None):
        """
        ONU-র RX power signal history নেওয়া।
        Frontend-এ time-series chart render করার জন্য।
        query param: hours=24 (কত ঘণ্টার data)
        """
        onu = self.get_object()
        hours = int(request.query_params.get('hours', 24))
        since = timezone.now() - timezone.timedelta(hours=hours)

        logs = ONUSignalLog.objects.filter(
            onu=onu,
            recorded_at__gte=since
        ).order_by('recorded_at').values(
            'recorded_at', 'rx_power', 'tx_power', 'olt_rx_power',
            'temperature', 'voltage', 'status'
        )

        return Response({
            'onu_id': onu.id,
            'serial': onu.serial_number,
            'hours':  hours,
            'count':  logs.count(),
            'data':   list(logs),
        })

    @action(detail=True, methods=['get'], url_path='events')
    def events(self, request, pk=None):
        """ONU-র event history দেখা।"""
        onu = self.get_object()
        events = ONUEvent.objects.filter(onu=onu).order_by('-created_at')[:50]
        return Response(ONUEventSerializer(events, many=True).data)


@extend_schema(tags=['OLT - Monitoring'])
class ONUSignalLogListView(generics.ListAPIView):
    """সব ONU-র signal log list (filter করা যাবে)।"""
    serializer_class = ONUSignalLogSerializer
    permission_classes = [IsAdminOrStaff]
    pagination_class = LargeResultsSetPagination
    filterset_fields = ['onu', 'status']

    def get_queryset(self):
        qs = ONUSignalLog.objects.select_related('onu').order_by('-recorded_at')
        olt_id = self.request.query_params.get('olt_id')
        if olt_id:
            qs = qs.filter(onu__olt_id=olt_id)
        return qs


@extend_schema(tags=['OLT - Critical'])
class CriticalONUListView(generics.ListAPIView):
    """
    Signal critical ONU তালিকা (RX power threshold-এর নিচে)।
    Dashboard-এর alert panel-এর জন্য।
    """
    serializer_class = ONUListSerializer
    permission_classes = [IsAdminOrStaff]

    def get_queryset(self):
        from django.db.models import F
        return ONU.objects.filter(
            status='online',
            rx_power__isnull=False,
            rx_power__lt=F('rx_power_threshold_crit'),
        ).select_related('olt', 'port', 'client').order_by('rx_power')


@extend_schema(tags=['OLT - Config'])
class OLTSNMPOIDProfileViewSet(viewsets.ModelViewSet):
    """Vendor-specific SNMP OID Profile management।"""
    queryset = OLTSNMPOIDProfile.objects.all()
    serializer_class = OLTSNMPOIDProfileSerializer
    permission_classes = [IsAdminUser]
