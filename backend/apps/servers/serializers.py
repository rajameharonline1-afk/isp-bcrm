# ফাইল: backend/apps/servers/serializers.py
# এই ফাইলটি Mikrotik Router ও FreeRADIUS-এর সব API serializers ধারণ করে।

from rest_framework import serializers
from .models import (
    MikrotikRouter, RouterPPPoEProfile, RouterBackup,
    RouterConnectionLog, RadiusServer,
)


class MikrotikRouterSerializer(serializers.ModelSerializer):
    """Mikrotik Router তৈরি ও update করার serializer।"""

    # Password write-only (response-এ দেখা যাবে না)
    api_password = serializers.CharField(write_only=True)
    ssh_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    nas_secret = serializers.CharField(write_only=True, required=False, allow_blank=True)
    zone_name = serializers.CharField(source='zone.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = MikrotikRouter
        fields = [
            'id', 'name', 'ip_address', 'api_port', 'api_username', 'api_password',
            'ssh_port', 'ssh_username', 'ssh_password',
            'nas_identifier', 'nas_secret', 'nas_port',
            'description', 'status', 'status_display',
            'last_checked', 'last_backup', 'zone', 'zone_name',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['status', 'last_checked', 'last_backup', 'created_at', 'updated_at']


class MikrotikRouterListSerializer(serializers.ModelSerializer):
    """Router list-এর জন্য সংক্ষিপ্ত serializer।"""
    zone_name = serializers.CharField(source='zone.name', read_only=True)

    class Meta:
        model = MikrotikRouter
        fields = ['id', 'name', 'ip_address', 'status', 'zone_name', 'is_active', 'last_checked']


class RouterPPPoEProfileSerializer(serializers.ModelSerializer):
    """PPPoE Profile-এর serializer।"""
    router_name = serializers.CharField(source='router.name', read_only=True)
    package_name = serializers.CharField(source='package.name', read_only=True)

    class Meta:
        model = RouterPPPoEProfile
        fields = [
            'id', 'router', 'router_name', 'profile_name', 'local_address',
            'remote_address', 'rate_limit', 'dns_server', 'package', 'package_name',
            'synced_at', 'created_at',
        ]


class RouterBackupSerializer(serializers.ModelSerializer):
    """Router Backup-এর serializer।"""
    router_name = serializers.CharField(source='router.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)

    class Meta:
        model = RouterBackup
        fields = [
            'id', 'router', 'router_name', 'backup_file', 'file_name',
            'file_size', 'note', 'created_by', 'created_by_name', 'created_at',
        ]


class RouterConnectionLogSerializer(serializers.ModelSerializer):
    """Router connection log-এর serializer।"""
    router_name = serializers.CharField(source='router.name', read_only=True)
    performed_by_name = serializers.CharField(source='performed_by.full_name', read_only=True)

    class Meta:
        model = RouterConnectionLog
        fields = [
            'id', 'router', 'router_name', 'action', 'target',
            'is_success', 'message', 'performed_by', 'performed_by_name', 'created_at',
        ]


class RadiusServerSerializer(serializers.ModelSerializer):
    """RADIUS Server-এর serializer।"""
    secret = serializers.CharField(write_only=True)

    class Meta:
        model = RadiusServer
        fields = ['id', 'name', 'host', 'auth_port', 'acct_port', 'coa_port',
                  'secret', 'description', 'is_active', 'created_at']


# =============================================
# Action Serializers (API actions-এর input validation)
# =============================================

class PPPoEUserCreateSerializer(serializers.Serializer):
    """নতুন PPPoE user তৈরির জন্য input serializer।"""
    router_id = serializers.IntegerField()
    username = serializers.CharField(max_length=64)
    password = serializers.CharField(max_length=64)
    profile = serializers.CharField(max_length=100)
    service = serializers.ChoiceField(choices=['pppoe', 'any', 'pptp', 'l2tp'], default='pppoe')
    comment = serializers.CharField(max_length=255, required=False, allow_blank=True)
    local_address = serializers.IPAddressField(required=False, allow_blank=True)
    remote_address = serializers.CharField(max_length=100, required=False, allow_blank=True)

    # FreeRADIUS-এও create করতে হবে কিনা
    sync_to_radius = serializers.BooleanField(default=True)
    radius_group = serializers.CharField(max_length=64, required=False, allow_blank=True)


class PPPoEUserActionSerializer(serializers.Serializer):
    """PPPoE user enable/disable/disconnect-এর জন্য input serializer।"""
    router_id = serializers.IntegerField()
    username = serializers.CharField(max_length=64)
    sync_to_radius = serializers.BooleanField(default=True)


class PPPoEProfileChangeSerializer(serializers.Serializer):
    """PPPoE profile/package পরিবর্তনের জন্য serializer।"""
    router_id = serializers.IntegerField()
    username = serializers.CharField(max_length=64)
    new_profile = serializers.CharField(max_length=100)
    new_radius_group = serializers.CharField(max_length=64, required=False)
    sync_to_radius = serializers.BooleanField(default=True)


class RouterBackupRequestSerializer(serializers.Serializer):
    """Router backup request-এর serializer।"""
    router_id = serializers.IntegerField()
    note = serializers.CharField(max_length=255, required=False, allow_blank=True)


class BulkImportSerializer(serializers.Serializer):
    """Excel file থেকে bulk client import-এর serializer।"""
    router_id = serializers.IntegerField(required=False)
    excel_file = serializers.FileField()
    sync_to_radius = serializers.BooleanField(default=True)
    dry_run = serializers.BooleanField(default=False)  # preview mode (আসলে save করবে না)
