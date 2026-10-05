# ফাইল: backend/apps/billing/admin.py
from django.contrib import admin
from .models import Billing, Payment


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ['payment_date', 'created_at']
    fields = ['amount', 'method', 'transaction_id', 'collected_by', 'note', 'payment_date']


@admin.register(Billing)
class BillingAdmin(admin.ModelAdmin):
    list_display  = ['client', 'bill_month', 'payable_amount', 'paid_amount',
                     'due_amount', 'status', 'due_date']
    list_filter   = ['status', 'bill_month']
    search_fields = ['client__full_name', 'client__username', 'client__phone']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['client', 'generated_by']
    inlines = [PaymentInline]
    ordering = ['-bill_month', '-created_at']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display  = ['client', 'amount', 'method', 'transaction_id', 'collected_by', 'payment_date']
    list_filter   = ['method', 'payment_date']
    search_fields = ['client__full_name', 'client__username', 'transaction_id']
    readonly_fields = ['created_at']
    raw_id_fields = ['client', 'billing', 'collected_by']
    ordering = ['-created_at']
