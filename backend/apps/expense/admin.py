# ফাইল: backend/apps/expense/admin.py
from django.contrib import admin
from .models import ExpenseCategory, Expense


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'account_code', 'is_active']


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display  = ['category', 'amount', 'date', 'method', 'payee', 'recorded_by']
    list_filter   = ['category', 'method', 'date']
    search_fields = ['description', 'reference_no', 'payee']
    date_hierarchy = 'date'
    raw_id_fields  = ['approved_by', 'recorded_by']
