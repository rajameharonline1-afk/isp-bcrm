# ফাইল: backend/apps/sms/admin.py
# এই ফাইলটি sms models Django Admin-এ register করে (gateway secret বাদে)।

from django.contrib import admin
from .models import SMSGateway, SMSTemplate, SMSGroup, SMSMessage

admin.site.register(SMSTemplate)
admin.site.register(SMSGroup)


@admin.register(SMSGateway)
class SMSGatewayAdmin(admin.ModelAdmin):
    exclude = ('api_key', 'secret_key')
    list_display = ('name', 'is_default', 'is_active')


@admin.register(SMSMessage)
class SMSMessageAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('recipient',)
