# ফাইল: backend/apps/servers/views.py
# এই ফাইলটি Mikrotik Router ও FreeRADIUS-এর সব API views ধারণ করে।

import io
import pandas as pd
from django.utils import timezone
from django.http import HttpResponse
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import MikrotikRouter, RouterPPPoEProfile, RouterBackup, RouterConnectionLog, RadiusServer
from .serializers import (
    MikrotikRouterSerializer, MikrotikRouterListSerializer,
    RouterPPPoEProfileSerializer, RouterBackupSerializer,
    RouterConnectionLogSerializer, RadiusServerSerializer,
    PPPoEUserCreateSerializer, PPPoEUserActionSerializer,
    PPPoEProfileChangeSerializer, RouterBackupRequestSerializer,
    BulkImportSerializer,
)
from .services import MikrotikService, MikrotikAPIError, FreeRADIUSService, FreeRADIUSError
from apps.accounts.permissions import IsAdminOrStaff, IsAdminUser
from utils.pagination import StandardResultsSetPagination


def _log_router_action(router, action, target, success, message, user):
    """Router action log save করার helper function।"""
    RouterConnectionLog.objects.create(
        router=router,
        action=action,
        target=target,
        is_success=success,
        message=message,
        performed_by=user,
    )


@extend_schema(tags=['Servers - Mikrotik'])
class MikrotikRouterViewSet(viewsets.ModelViewSet):
    """
    Mikrotik Router-এর CRUD operations এবং সব router management actions।
    PPPoE user create/enable/disable/disconnect, backup, import সব এখানে।
    """
    queryset = MikrotikRouter.objects.filter(is_active=True).select_related('zone')
    permission_classes = [IsAdminOrStaff]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['status', 'zone', 'is_active']
    search_fields = ['name', 'ip_address', 'description']

    def get_serializer_class(self):
        if self.action == 'list':
            return MikrotikRouterListSerializer
        return MikrotikRouterSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    # =============================================
    # Router Status Actions
    # =============================================

    @action(detail=True, methods=['post'], url_path='test-connection')
    def test_connection(self, request, pk=None):
        """Router-এ test connection করে online/offline status আপডেট করে।"""
        router = self.get_object()

        try:
            service = MikrotikService(**router.get_api_credentials())
            result = service.test_connection()

            # Router status আপডেট করা
            router.status = MikrotikRouter.RouterStatus.ONLINE if result['success'] else MikrotikRouter.RouterStatus.OFFLINE
            router.last_checked = timezone.now()
            router.save(update_fields=['status', 'last_checked'])

            _log_router_action(
                router, RouterConnectionLog.ActionType.CONNECT_TEST,
                router.ip_address, result['success'],
                result.get('error', f"Version: {result.get('version')}"),
                request.user,
            )
            return Response(result)

        except MikrotikAPIError as e:
            router.status = MikrotikRouter.RouterStatus.OFFLINE
            router.last_checked = timezone.now()
            router.save(update_fields=['status', 'last_checked'])
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='system-info')
    def system_info(self, request, pk=None):
        """Router-এর CPU, memory, uptime সহ system information দেখা।"""
        router = self.get_object()
        try:
            service = MikrotikService(**router.get_api_credentials())
            info = service.get_system_resource()
            return Response(info)
        except MikrotikAPIError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='active-connections')
    def active_connections(self, request, pk=None):
        """Router-এ এখন কতজন connected আছে এবং তাদের তথ্য।"""
        router = self.get_object()
        try:
            service = MikrotikService(**router.get_api_credentials())
            connections = service.get_active_connections()
            return Response({'count': len(connections), 'connections': connections})
        except MikrotikAPIError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], url_path='traffic')
    def interface_traffic(self, request, pk=None):
        """Router-এর সব interface-এর live traffic data।"""
        router = self.get_object()
        interface = request.query_params.get('interface', 'all')
        try:
            service = MikrotikService(**router.get_api_credentials())
            traffic = service.get_interface_traffic(interface)
            return Response({'interfaces': traffic})
        except MikrotikAPIError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # =============================================
    # PPPoE Secret Management
    # =============================================

    @action(detail=False, methods=['post'], url_path='pppoe/create')
    def create_pppoe_user(self, request):
        """
        Mikrotik ও FreeRADIUS উভয়তেই নতুন PPPoE user তৈরি করে।
        নতুন client connection দেওয়ার সময় call করা হয়।
        """
        serializer = PPPoEUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            router = MikrotikRouter.objects.get(id=data['router_id'], is_active=True)
        except MikrotikRouter.DoesNotExist:
            return Response({'error': 'Router পাওয়া যায়নি।'}, status=status.HTTP_404_NOT_FOUND)

        errors = []
        results = {}

        # Mikrotik-এ PPPoE secret তৈরি করা
        try:
            service = MikrotikService(**router.get_api_credentials())
            mikrotik_result = service.create_pppoe_secret(
                username=data['username'],
                password=data['password'],
                profile=data['profile'],
                service=data.get('service', 'pppoe'),
                comment=data.get('comment', ''),
                local_address=data.get('local_address', ''),
                remote_address=data.get('remote_address', ''),
            )
            results['mikrotik'] = mikrotik_result

            _log_router_action(
                router, RouterConnectionLog.ActionType.PPP_CREATE,
                data['username'], mikrotik_result['success'],
                mikrotik_result.get('message') or mikrotik_result.get('error', ''),
                request.user,
            )
        except MikrotikAPIError as e:
            errors.append(f"Mikrotik error: {e}")
            results['mikrotik'] = {'success': False, 'error': str(e)}

        # FreeRADIUS-এও তৈরি করা (sync_to_radius=True হলে)
        if data.get('sync_to_radius', True):
            radius_group = data.get('radius_group', data['profile'])
            try:
                radius_result = FreeRADIUSService.create_user(
                    username=data['username'],
                    password=data['password'],
                    group=radius_group,
                )
                results['radius'] = radius_result
            except FreeRADIUSError as e:
                errors.append(f"RADIUS error: {e}")
                results['radius'] = {'success': False, 'error': str(e)}

        overall_success = results.get('mikrotik', {}).get('success', False)
        return Response({
            'success': overall_success,
            'results': results,
            'errors': errors,
        }, status=status.HTTP_201_CREATED if overall_success else status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='pppoe/enable')
    def enable_pppoe_user(self, request):
        """Mikrotik ও RADIUS উভয়তেই PPPoE user enable করে।"""
        serializer = PPPoEUserActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            router = MikrotikRouter.objects.get(id=data['router_id'])
        except MikrotikRouter.DoesNotExist:
            return Response({'error': 'Router পাওয়া যায়নি।'}, status=status.HTTP_404_NOT_FOUND)

        results = {}

        # Mikrotik enable
        try:
            service = MikrotikService(**router.get_api_credentials())
            results['mikrotik'] = service.enable_pppoe_secret(data['username'])
            _log_router_action(
                router, RouterConnectionLog.ActionType.PPP_ENABLE,
                data['username'], True, f"Enabled: {data['username']}", request.user,
            )
        except MikrotikAPIError as e:
            results['mikrotik'] = {'success': False, 'error': str(e)}

        # RADIUS enable
        if data.get('sync_to_radius', True):
            try:
                results['radius'] = FreeRADIUSService.enable_user(data['username'])
            except FreeRADIUSError as e:
                results['radius'] = {'success': False, 'error': str(e)}

        return Response({'success': True, 'results': results})

    @action(detail=False, methods=['post'], url_path='pppoe/disable')
    def disable_pppoe_user(self, request):
        """Mikrotik ও RADIUS উভয়তেই PPPoE user disable করে এবং active session disconnect করে।"""
        serializer = PPPoEUserActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            router = MikrotikRouter.objects.get(id=data['router_id'])
        except MikrotikRouter.DoesNotExist:
            return Response({'error': 'Router পাওয়া যায়নি।'}, status=status.HTTP_404_NOT_FOUND)

        results = {}

        # Mikrotik disable (active session-ও disconnect হবে)
        try:
            service = MikrotikService(**router.get_api_credentials())
            results['mikrotik'] = service.disable_pppoe_secret(data['username'])
            _log_router_action(
                router, RouterConnectionLog.ActionType.PPP_DISABLE,
                data['username'], True, f"Disabled: {data['username']}", request.user,
            )
        except MikrotikAPIError as e:
            results['mikrotik'] = {'success': False, 'error': str(e)}

        # RADIUS disable
        if data.get('sync_to_radius', True):
            try:
                results['radius'] = FreeRADIUSService.disable_user(data['username'])
            except FreeRADIUSError as e:
                results['radius'] = {'success': False, 'error': str(e)}

        return Response({'results': results})

    @action(detail=False, methods=['post'], url_path='pppoe/disconnect')
    def disconnect_pppoe_user(self, request):
        """Active PPPoE user forcefully disconnect করে (session শেষ করে)।"""
        serializer = PPPoEUserActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            router = MikrotikRouter.objects.get(id=data['router_id'])
        except MikrotikRouter.DoesNotExist:
            return Response({'error': 'Router পাওয়া যায়নি।'}, status=status.HTTP_404_NOT_FOUND)

        try:
            service = MikrotikService(**router.get_api_credentials())
            result = service.disconnect_active_user(data['username'])
            _log_router_action(
                router, RouterConnectionLog.ActionType.PPP_DISCONNECT,
                data['username'], result['success'], result.get('message', ''), request.user,
            )
            return Response(result)
        except MikrotikAPIError as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='pppoe/change-profile')
    def change_pppoe_profile(self, request):
        """PPPoE user-এর profile (package/speed) পরিবর্তন করে।"""
        serializer = PPPoEProfileChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            router = MikrotikRouter.objects.get(id=data['router_id'])
        except MikrotikRouter.DoesNotExist:
            return Response({'error': 'Router পাওয়া যায়নি।'}, status=status.HTTP_404_NOT_FOUND)

        results = {}

        # Mikrotik profile change
        try:
            service = MikrotikService(**router.get_api_credentials())
            results['mikrotik'] = service.change_pppoe_profile(data['username'], data['new_profile'])
        except MikrotikAPIError as e:
            results['mikrotik'] = {'success': False, 'error': str(e)}

        # RADIUS group change
        if data.get('sync_to_radius') and data.get('new_radius_group'):
            try:
                results['radius'] = FreeRADIUSService.change_user_package(
                    data['username'], data['new_radius_group']
                )
            except FreeRADIUSError as e:
                results['radius'] = {'success': False, 'error': str(e)}

        return Response({'results': results})

    @action(detail=True, methods=['get'], url_path='pppoe-secrets')
    def get_pppoe_secrets(self, request, pk=None):
        """Router-এর সব PPPoE secret তালিকা দেখা।"""
        router = self.get_object()
        try:
            service = MikrotikService(**router.get_api_credentials())
            secrets = service.get_all_pppoe_secrets()
            return Response({'count': len(secrets), 'secrets': secrets})
        except MikrotikAPIError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # =============================================
    # Profile Sync
    # =============================================

    @action(detail=True, methods=['post'], url_path='sync-profiles')
    def sync_pppoe_profiles(self, request, pk=None):
        """Router থেকে সব PPPoE profile sync করে database-এ save করে।"""
        router = self.get_object()
        try:
            service = MikrotikService(**router.get_api_credentials())
            profiles = service.get_all_pppoe_profiles()

            synced = 0
            for p in profiles:
                if p['name'] in ['default', 'default-encryption']:
                    continue
                RouterPPPoEProfile.objects.update_or_create(
                    router=router,
                    profile_name=p['name'],
                    defaults={
                        'local_address': p.get('local_address', ''),
                        'remote_address': p.get('remote_address', ''),
                        'rate_limit': p.get('rate_limit', ''),
                        'dns_server': p.get('dns_server', ''),
                        'synced_at': timezone.now(),
                    }
                )
                synced += 1

            _log_router_action(
                router, RouterConnectionLog.ActionType.PROFILE_SYNC,
                '', True, f"{synced} profiles synced", request.user,
            )
            return Response({'success': True, 'synced_profiles': synced})

        except MikrotikAPIError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # =============================================
    # Router Backup
    # =============================================

    @action(detail=False, methods=['post'], url_path='backup')
    def create_backup(self, request):
        """Router backup তৈরি করে (Celery task-এ চালানো হয়)।"""
        serializer = RouterBackupRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            router = MikrotikRouter.objects.get(id=data['router_id'])
        except MikrotikRouter.DoesNotExist:
            return Response({'error': 'Router পাওয়া যায়নি।'}, status=status.HTTP_404_NOT_FOUND)

        # Celery task-এ backup চালানো
        from .tasks import router_backup_task
        task = router_backup_task.delay(router.id, request.user.id, data.get('note', ''))

        return Response({
            'success': True,
            'message': 'Backup task শুরু হয়েছে। কিছুক্ষণ পর Router Backup তালিকায় দেখা যাবে।',
            'task_id': task.id,
        })

    # =============================================
    # Import from Mikrotik & Bulk Import
    # =============================================

    @action(detail=True, methods=['get'], url_path='import-preview')
    def import_from_mikrotik_preview(self, request, pk=None):
        """
        Mikrotik থেকে সব PPPoE secret import করার আগে preview দেখানো।
        কোন user ইতিমধ্যে আছে এবং কোনটি নতুন তা দেখা যাবে।
        """
        from apps.clients.models import Client  # noqa - lazy import

        router = self.get_object()
        try:
            service = MikrotikService(**router.get_api_credentials())
            secrets = service.get_all_pppoe_secrets()

            # Database-এ কোন username আছে check করা
            existing_usernames = set(
                Client.objects.values_list('username', flat=True)
            )

            preview = []
            for s in secrets:
                preview.append({
                    **s,
                    'already_exists': s['username'] in existing_usernames,
                })

            return Response({
                'total': len(preview),
                'new': sum(1 for p in preview if not p['already_exists']),
                'existing': sum(1 for p in preview if p['already_exists']),
                'secrets': preview,
            })

        except MikrotikAPIError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='bulk-import-excel',
            parser_classes=[MultiPartParser])
    def bulk_import_from_excel(self, request):
        """
        Excel (.xlsx) ফাইল থেকে bulk client import করে।
        প্রতিটি row-এর জন্য Mikrotik এবং RADIUS-এ user তৈরি করে।
        """
        serializer = BulkImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        excel_file = data['excel_file']

        try:
            df = pd.read_excel(io.BytesIO(excel_file.read()))
        except Exception as e:
            return Response({'error': f'Excel file পড়া যাচ্ছে না: {e}'}, status=status.HTTP_400_BAD_REQUEST)

        # Expected columns check
        required_cols = ['username', 'password', 'profile']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return Response({
                'error': f'Excel-এ এই column গুলো নেই: {", ".join(missing_cols)}'
            }, status=status.HTTP_400_BAD_REQUEST)

        # dry_run mode-এ শুধু preview দেওয়া
        if data.get('dry_run'):
            preview = df[required_cols].to_dict('records')
            return Response({'dry_run': True, 'total_rows': len(preview), 'preview': preview[:10]})

        # Celery task-এ import চালানো
        from .tasks import bulk_import_task
        records = df.fillna('').to_dict('records')
        router_id = data.get('router_id')
        task = bulk_import_task.delay(
            records, router_id, request.user.id, data.get('sync_to_radius', True)
        )

        return Response({
            'success': True,
            'message': f'{len(records)} টি record import শুরু হয়েছে।',
            'task_id': task.id,
        })


@extend_schema(tags=['Servers - RADIUS'])
class RadiusServerViewSet(viewsets.ModelViewSet):
    """FreeRADIUS server management।"""
    queryset = RadiusServer.objects.filter(is_active=True)
    serializer_class = RadiusServerSerializer
    permission_classes = [IsAdminUser]


@extend_schema(tags=['Servers - Logs'])
class RouterConnectionLogListView(generics.ListAPIView):
    """Router connection log তালিকা।"""
    serializer_class = RouterConnectionLogSerializer
    permission_classes = [IsAdminOrStaff]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['router', 'action', 'is_success']
    search_fields = ['target', 'message']

    def get_queryset(self):
        return RouterConnectionLog.objects.select_related('router', 'performed_by').order_by('-created_at')


@extend_schema(tags=['Servers - Backup'])
class RouterBackupListView(generics.ListAPIView):
    """Router backup তালিকা।"""
    serializer_class = RouterBackupSerializer
    permission_classes = [IsAdminOrStaff]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['router']

    def get_queryset(self):
        return RouterBackup.objects.select_related('router', 'created_by').order_by('-created_at')


@extend_schema(tags=['Servers - RADIUS'])
class RadiusUserInfoView(generics.GenericAPIView):
    """RADIUS user-এর সব তথ্য ও session history দেখা।"""
    permission_classes = [IsAdminOrStaff]

    def get(self, request, username):
        try:
            info = FreeRADIUSService.get_user_info(username)
            return Response(info)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=['Servers - RADIUS'])
class RadiusActiveSessionsView(generics.GenericAPIView):
    """FreeRADIUS-এ এখন active সব session দেখা।"""
    permission_classes = [IsAdminOrStaff]

    def get(self, request):
        try:
            sessions = FreeRADIUSService.get_active_sessions()
            return Response({'count': len(sessions), 'sessions': sessions})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
