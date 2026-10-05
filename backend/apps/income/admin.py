# ফাইল: backend/apps/income/admin.py
from django.contrib import admin
from .models import IncomeCategory, Income


@admin.register(IncomeCategory)
class IncomeCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'account_code', 'is_active']


@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display  = ['category', 'amount', 'date', 'method', 'reference_no', 'collected_by']
    list_filter   = ['category', 'method', 'date']
    search_fields = ['description', 'reference_no']
    date_hierarchy = 'date'
    raw_id_fields  = ['client', 'billing', 'collected_by']
