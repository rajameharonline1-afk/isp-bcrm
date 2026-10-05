# ফাইল: backend/apps/olt/admin.py
# এই ফাইলটি OLT module-এর সব models Django Admin-এ register করে।

from django.contrib import admin
from .models import OLT, OLTPort, ONU, ONUSignalLog, ONUEvent, OLTSNMPOIDProfile


@admin.register(OLT)
class OLTAdmin(admin.ModelAdmin):
    list_display = ['name', 'ip_address', 'vendor', 'status', 'total_onus', 'online_onus', 'last_polled', 'is_active']
    list_filter  = ['vendor', 'status', 'is_active', 'zone']
    search_fields = ['name', 'ip_address', 'model']
    readonly_fields = ['status', 'last_polled', 'total_onus', 'online_onus', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic', {'fields': ('name', 'ip_address', 'vendor', 'model', 'zone', 'description', 'is_active')}),
        ('SSH', {'fields': ('ssh_port', 'ssh_username', 'ssh_password', 'enable_password', 'use_telnet', 'telnet_port'), 'classes': ('collapse',)}),
        ('SNMP', {'fields': ('snmp_version', 'snmp_community', 'snmp_port', 'snmp_timeout', 'snmp_retries'), 'classes': ('collapse',)}),
        ('SNMPv3', {'fields': ('snmp_v3_username', 'snmp_v3_auth_key', 'snmp_v3_priv_key', 'snmp_v3_auth_proto', 'snmp_v3_priv_proto'), 'classes': ('collapse',)}),
        ('Status', {'fields': ('status', 'last_polled', 'total_onus', 'online_onus')}),
    )


@admin.register(OLTPort)
class OLTPortAdmin(admin.ModelAdmin):
    list_display  = ['olt', 'frame', 'slot', 'port', 'port_type', 'current_onus', 'max_onus', 'is_active']
    list_filter   = ['olt', 'port_type', 'is_active']
    search_fields = ['olt__name', 'description', 'pon_index']


@admin.register(ONU)
class ONUAdmin(admin.ModelAdmin):
    list_display  = ['serial_number', 'olt', 'port', 'onu_id', 'status', 'rx_power', 'last_seen']
    list_filter   = ['status', 'olt', 'pending_action']
    search_fields = ['serial_number', 'mac_address', 'description', 'pppoe_username']
    readonly_fields = ['rx_power', 'tx_power', 'olt_rx_power', 'temperature', 'voltage',
                       'last_seen', 'last_polled', 'authorized_at', 'created_at', 'updated_at']


@admin.register(ONUSignalLog)
class ONUSignalLogAdmin(admin.ModelAdmin):
    list_display  = ['onu', 'rx_power', 'tx_power', 'status', 'recorded_at']
    list_filter   = ['status']
    date_hierarchy = 'recorded_at'
    search_fields = ['onu__serial_number']


@admin.register(ONUEvent)
class ONUEventAdmin(admin.ModelAdmin):
    list_display  = ['onu', 'event_type', 'rx_power', 'triggered_by', 'created_at']
    list_filter   = ['event_type']
    search_fields = ['onu__serial_number', 'details']


@admin.register(OLTSNMPOIDProfile)
class OLTSNMPOIDProfileAdmin(admin.ModelAdmin):
    list_display = ['vendor', 'updated_at']
