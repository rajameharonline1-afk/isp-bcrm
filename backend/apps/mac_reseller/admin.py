# ফাইল: backend/apps/mac_reseller/admin.py
# এই ফাইলটি MAC Reseller models Django Admin-এ register করে।

from django.contrib import admin
from .models import (
    MACReseller, MACResellerPackage, MACResellerTariffConfig,
    MACResellerFunding, ClientPGWPayment, PGWTransactionSettlement,
    MACResellerNotice,
)


@admin.register(MACReseller)
class MACResellerAdmin(admin.ModelAdmin):
    list_display  = ['name', 'contact', 'email', 'balance', 'status', 'created_at']
    list_filter   = ['status']
    search_fields = ['name', 'contact', 'email']
    readonly_fields = ['balance', 'created_at', 'updated_at']


@admin.register(MACResellerPackage)
class MACResellerPackageAdmin(admin.ModelAdmin):
    list_display  = ['name', 'bandwidth_down', 'bandwidth_up', 'retail_price', 'duration_days', 'is_active']
    list_filter   = ['is_active']
    search_fields = ['name']


@admin.register(MACResellerTariffConfig)
class MACResellerTariffConfigAdmin(admin.ModelAdmin):
    list_display  = ['reseller', 'package', 'reseller_price', 'max_retail_price', 'is_active', 'effective_from']
    list_filter   = ['is_active', 'reseller']
    search_fields = ['reseller__name', 'package__name']


@admin.register(MACResellerFunding)
class MACResellerFundingAdmin(admin.ModelAdmin):
    list_display  = ['reseller', 'amount', 'payment_method', 'status', 'balance_before', 'balance_after', 'funded_at']
    list_filter   = ['status', 'payment_method']
    search_fields = ['reseller__name', 'transaction_id']
    readonly_fields = ['balance_before', 'balance_after', 'funded_at']


@admin.register(ClientPGWPayment)
class ClientPGWPaymentAdmin(admin.ModelAdmin):
    list_display  = ['client', 'reseller', 'gateway', 'amount', 'status', 'order_id', 'created_at']
    list_filter   = ['status', 'gateway']
    search_fields = ['client__username', 'order_id', 'pgw_transaction_id']
    readonly_fields = ['order_id', 'created_at', 'updated_at']


@admin.register(PGWTransactionSettlement)
class PGWTransactionSettlementAdmin(admin.ModelAdmin):
    list_display  = ['reseller', 'payment_count', 'total_amount', 'net_settlement', 'status', 'settlement_date']
    list_filter   = ['status']
    search_fields = ['reseller__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(MACResellerNotice)
class MACResellerNoticeAdmin(admin.ModelAdmin):
    list_display  = ['title', 'notice_type', 'is_active', 'publish_at', 'expire_at', 'created_at']
    list_filter   = ['notice_type', 'is_active']
    search_fields = ['title', 'content']
    filter_horizontal = ['target_resellers']
