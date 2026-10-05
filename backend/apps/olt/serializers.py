# ফাইল: backend/apps/olt/serializers.py
# এই ফাইলটি OLT, ONU এবং monitoring data-এর সব API serializers ধারণ করে।

from rest_framework import serializers
from .models import OLT, OLTPort, ONU, ONUSignalLog, ONUEvent, OLTSNMPOIDProfile


class OLTSerializer(serializers.ModelSerializer):
    """OLT device তৈরি ও update-এর serializer।"""
    ssh_password    = serializers.CharField(write_only=True, required=False, allow_blank=True)
    snmp_community  = serializers.CharField(write_only=True, required=False)
    enable_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    snmp_v3_auth_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    snmp_v3_priv_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    zone_name       = serializers.CharField(source='zone.name', read_only=True)
    vendor_display  = serializers.CharField(source='get_vendor_display', read_only=True)
    status_display  = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = OLT
        fields = [
            'id', 'name', 'ip_address', 'vendor', 'vendor_display', 'model', 'description',
            'ssh_port', 'ssh_username', 'ssh_password', 'enable_password', 'use_telnet', 'telnet_port',
            'snmp_version', 'snmp_community', 'snmp_port', 'snmp_timeout', 'snmp_retries',
            'snmp_v3_username', 'snmp_v3_auth_key', 'snmp_v3_priv_key',
            'snmp_v3_auth_proto', 'snmp_v3_priv_proto',
            'zone', 'zone_name', 'status', 'status_display',
            'last_polled', 'total_onus', 'online_onus',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['status', 'last_polled', 'total_onus', 'online_onus', 'created_at', 'updated_at']


class OLTListSerializer(serializers.ModelSerializer):
    """OLT list-এর সংক্ষিপ্ত serializer।"""
    zone_name      = serializers.CharField(source='zone.name', read_only=True)
    vendor_display = serializers.CharField(source='get_vendor_display', read_only=True)

    class Meta:
        model = OLT
        fields = ['id', 'name', 'ip_address', 'vendor', 'vendor_display',
                  'status', 'zone_name', 'total_onus', 'online_onus', 'last_polled', 'is_active']


class OLTPortSerializer(serializers.ModelSerializer):
    olt_name   = serializers.CharField(source='olt.name', read_only=True)
    port_label = serializers.CharField(read_only=True)

    class Meta:
        model = OLTPort
        fields = ['id', 'olt', 'olt_name', 'port_type', 'frame', 'slot', 'port',
                  'pon_index', 'description', 'max_onus', 'current_onus',
                  'port_label', 'is_active', 'synced_at']


class ONUSerializer(serializers.ModelSerializer):
    """ONU সম্পূর্ণ তথ্য serializer।"""
    olt_name         = serializers.CharField(source='olt.name', read_only=True)
    port_label       = serializers.CharField(source='port.port_label', read_only=True)
    client_name      = serializers.CharField(source='client.full_name', read_only=True)
    client_phone     = serializers.CharField(source='client.phone', read_only=True)
    rx_power_status  = serializers.CharField(read_only=True)
    is_signal_critical = serializers.BooleanField(read_only=True)
    status_display   = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ONU
        fields = [
            'id', 'olt', 'olt_name', 'port', 'port_label', 'onu_id',
            'serial_number', 'mac_address', 'vendor', 'model', 'description',
            'rx_power', 'tx_power', 'olt_rx_power', 'temperature', 'voltage', 'bias_current', 'distance',
            'rx_power_threshold_warn', 'rx_power_threshold_crit',
            'rx_power_status', 'is_signal_critical',
            'status', 'status_display', 'pending_action',
            'ip_address', 'pppoe_username',
            'client', 'client_name', 'client_phone',
            'last_seen', 'authorized_at', 'last_polled', 'created_at',
        ]
        read_only_fields = [
            'rx_power', 'tx_power', 'olt_rx_power', 'temperature', 'voltage',
            'status', 'pending_action', 'last_seen', 'last_polled', 'created_at',
        ]


class ONUListSerializer(serializers.ModelSerializer):
    """ONU list-এর সংক্ষিপ্ত serializer।"""
    port_label      = serializers.CharField(source='port.port_label', read_only=True)
    client_name     = serializers.CharField(source='client.full_name', read_only=True)
    rx_power_status = serializers.CharField(read_only=True)
    is_signal_critical = serializers.BooleanField(read_only=True)

    class Meta:
        model = ONU
        fields = [
            'id', 'onu_id', 'serial_number', 'port_label', 'status',
            'rx_power', 'tx_power', 'rx_power_status', 'is_signal_critical',
            'temperature', 'client_name', 'last_seen', 'pending_action',
        ]


class ONUSignalLogSerializer(serializers.ModelSerializer):
    """ONU signal log serializer (chart data-এর জন্য)।"""
    class Meta:
        model = ONUSignalLog
        fields = ['id', 'rx_power', 'tx_power', 'olt_rx_power', 'temperature', 'voltage', 'status', 'recorded_at']


class ONUEventSerializer(serializers.ModelSerializer):
    """ONU event log serializer।"""
    triggered_by_name = serializers.CharField(source='triggered_by.full_name', read_only=True)
    event_display     = serializers.CharField(source='get_event_type_display', read_only=True)

    class Meta:
        model = ONUEvent
        fields = ['id', 'event_type', 'event_display', 'details', 'rx_power',
                  'triggered_by', 'triggered_by_name', 'created_at']


class OLTSNMPOIDProfileSerializer(serializers.ModelSerializer):
    """SNMP OID Profile serializer।"""
    class Meta:
        model = OLTSNMPOIDProfile
        fields = '__all__'


# =============================================
# Action Serializers
# =============================================

class ONUAuthorizeSerializer(serializers.Serializer):
    """ONU authorize request serializer।"""
    onu_id          = serializers.IntegerField()
    lineprofile_id  = serializers.IntegerField(default=10)
    srvprofile_id   = serializers.IntegerField(default=10)
    profile_name    = serializers.CharField(default='FTTH', max_length=64)
    desc            = serializers.CharField(max_length=200, required=False, allow_blank=True)


class ONUDeleteSerializer(serializers.Serializer):
    """ONU delete request serializer।"""
    onu_id  = serializers.IntegerField()
    confirm = serializers.BooleanField()

    def validate_confirm(self, value):
        if not value:
            raise serializers.ValidationError('Delete নিশ্চিত করতে confirm=true দিন।')
        return value


class ONUAddManualSerializer(serializers.Serializer):
    """Manual ONU যোগ করার serializer (SNMP discover-এর বাইরে)।"""
    olt_id        = serializers.IntegerField()
    port_id       = serializers.IntegerField()
    onu_id        = serializers.IntegerField()
    serial_number = serializers.CharField(max_length=64)
    description   = serializers.CharField(max_length=200, required=False, allow_blank=True)
    client_id     = serializers.IntegerField(required=False, allow_null=True)
