# ফাইল: backend/apps/servers/admin.py
# এই ফাইলটি Servers app-এর সব models Django Admin-এ register করে।

from django.contrib import admin
from .models import (
    MikrotikRouter, RouterPPPoEProfile, RouterBackup,
    RouterConnectionLog, RadiusServer, RadCheck, RadReply,
    RadUserGroup, RadGroupReply, RadAcct,
)


@admin.register(MikrotikRouter)
class MikrotikRouterAdmin(admin.ModelAdmin):
    list_display = ['name', 'ip_address', 'api_port', 'status', 'zone', 'is_active', 'last_checked']
    list_filter = ['status', 'is_active', 'zone']
    search_fields = ['name', 'ip_address', 'nas_identifier']
    readonly_fields = ['status', 'last_checked', 'last_backup', 'created_at', 'updated_at']

    # Password field গুলো list view-তে দেখাবে না
    exclude = []

    fieldsets = (
        ('Basic Info', {'fields': ('name', 'ip_address', 'api_port', 'api_username', 'api_password', 'zone', 'description')}),
        ('SSH Access', {'fields': ('ssh_port', 'ssh_username', 'ssh_password'), 'classes': ('collapse',)}),
        ('FreeRADIUS NAS', {'fields': ('nas_identifier', 'nas_secret', 'nas_port'), 'classes': ('collapse',)}),
        ('Status', {'fields': ('status', 'is_active', 'last_checked', 'last_backup')}),
    )


@admin.register(RouterConnectionLog)
class RouterConnectionLogAdmin(admin.ModelAdmin):
    list_display = ['router', 'action', 'target', 'is_success', 'performed_by', 'created_at']
    list_filter = ['action', 'is_success', 'router']
    search_fields = ['target', 'message']
    readonly_fields = ['created_at']


@admin.register(RouterBackup)
class RouterBackupAdmin(admin.ModelAdmin):
    list_display = ['router', 'file_name', 'file_size', 'created_by', 'created_at']
    list_filter = ['router']
    readonly_fields = ['created_at']


@admin.register(RadCheck)
class RadCheckAdmin(admin.ModelAdmin):
    list_display = ['username', 'attribute', 'op', 'value', 'created_at']
    search_fields = ['username']
    list_filter = ['attribute']

    def get_queryset(self, request):
        return super().get_queryset(request).using('radius')


@admin.register(RadUserGroup)
class RadUserGroupAdmin(admin.ModelAdmin):
    list_display = ['username', 'groupname', 'priority']
    search_fields = ['username', 'groupname']

    def get_queryset(self, request):
        return super().get_queryset(request).using('radius')


admin.site.register(RouterPPPoEProfile)
admin.site.register(RadiusServer)
admin.site.register(RadReply)
admin.site.register(RadGroupReply)
