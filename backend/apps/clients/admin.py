# ফাইল: backend/apps/clients/admin.py
from django.contrib import admin
from .models import Client, ClientStatusLog


class ClientStatusLogInline(admin.TabularInline):
    model = ClientStatusLog
    extra = 0
    readonly_fields = ['action', 'from_status', 'to_status', 'reason', 'performed_by', 'created_at']


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display  = ['full_name', 'username', 'phone', 'status', 'payment_status',
                     'package', 'zone', 'expiry_date', 'monthly_bill', 'due_amount']
    list_filter   = ['status', 'payment_status', 'zone', 'package', 'router',
                     'optical_fiber', 'app_enabled']
    search_fields = ['full_name', 'username', 'phone', 'email', 'nid']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    raw_id_fields = ['zone', 'subzone', 'box', 'thana', 'district',
                     'package', 'router', 'client_type', 'protocol']
    inlines = [ClientStatusLogInline]
    ordering = ['-created_at']

    fieldsets = (
        ('Personal Info', {
            'fields': ('full_name', 'father_name', 'phone', 'alt_phone', 'email', 'nid')
        }),
        ('Address', {
            'fields': ('house_name', 'house_no', 'road_no', 'address',
                       'thana', 'district', 'zone', 'subzone', 'box',
                       'map_lat', 'map_lng')
        }),
        ('Connection', {
            'fields': ('client_type', 'protocol', 'package', 'username',
                       'ip_address', 'mac_address', 'router', 'pppoe_profile')
        }),
        ('Billing', {
            'fields': ('bill_date', 'expiry_day', 'billing_start_month',
                       'connection_date', 'expiry_date', 'monthly_bill',
                       'discount', 'due_amount', 'advance_balance')
        }),
        ('Status', {
            'fields': ('status', 'payment_status', 'is_renewed', 'renewed_at')
        }),
        ('Hardware', {
            'fields': ('device', 'optical_fiber', 'cable_meter', 'vendor',
                       'serial_no', 'fiber_code', 'color_of_cord', 'device_purchase_date'),
            'classes': ('collapse',),
        }),
        ('Remote Management', {
            'fields': ('remote_mgmt_ip', 'remote_admin_user'),
            'classes': ('collapse',),
        }),
        ('Mobile App', {
            'fields': ('app_enabled', 'app_password', 'app_last_seen', 'app_registered_on'),
            'classes': ('collapse',),
        }),
        ('Documents', {
            'fields': ('photo', 'nid_photo', 'reg_form_pic'),
            'classes': ('collapse',),
        }),
        ('Meta', {
            'fields': ('notes', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(ClientStatusLog)
class ClientStatusLogAdmin(admin.ModelAdmin):
    list_display  = ['client', 'action', 'from_status', 'to_status', 'performed_by', 'created_at']
    list_filter   = ['action']
    readonly_fields = ['created_at']
    raw_id_fields = ['client', 'performed_by']
