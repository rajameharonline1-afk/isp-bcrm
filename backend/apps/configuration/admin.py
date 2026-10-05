# ফাইল: backend/apps/configuration/admin.py
# এই ফাইলটি configuration models Django Admin-এ register করে।

from django.contrib import admin
from .models import District, Upazila, Zone, SubZone, Box, Package, ConnectionType, ClientType, ProtocolType, BillingStatus


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    search_fields = ['name']


@admin.register(SubZone)
class SubZoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'zone', 'is_active', 'created_at']
    list_filter = ['zone', 'is_active']
    search_fields = ['name']


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ['name', 'package_type', 'download_speed', 'upload_speed', 'monthly_price', 'is_active']
    list_filter = ['package_type', 'is_active']
    search_fields = ['name', 'mikrotik_profile']


admin.site.register(Upazila)
admin.site.register(Box)
admin.site.register(ConnectionType)
admin.site.register(ClientType)
admin.site.register(ProtocolType)
admin.site.register(BillingStatus)
