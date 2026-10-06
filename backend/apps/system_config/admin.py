# ফাইল: backend/apps/system_config/admin.py
# এই ফাইলটি system_config models Django Admin-এ register করে (secret field বাদে)।

from django.contrib import admin
from .models import (
    CompanySetting, InvoiceSetting, EmailSetting, PaymentGateway,
    PaymentProcessingFee, SystemSetting,
)

admin.site.register(CompanySetting)
admin.site.register(InvoiceSetting)
admin.site.register(SystemSetting)
admin.site.register(PaymentProcessingFee)


@admin.register(EmailSetting)
class EmailSettingAdmin(admin.ModelAdmin):
    exclude = ('password',)


@admin.register(PaymentGateway)
class PaymentGatewayAdmin(admin.ModelAdmin):
    exclude = ('store_password', 'api_key', 'api_secret')
    list_display = ('provider', 'is_active', 'is_sandbox')
