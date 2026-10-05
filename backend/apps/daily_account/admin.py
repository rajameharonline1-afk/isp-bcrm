# ফাইল: backend/apps/daily_account/admin.py
from django.contrib import admin
from .models import DailyAccount


@admin.register(DailyAccount)
class DailyAccountAdmin(admin.ModelAdmin):
    list_display  = ['date', 'total_income', 'total_expense', 'net_profit_loss',
                     'opening_cash', 'closing_cash', 'status']
    list_filter   = ['status']
    readonly_fields = ['closed_by', 'closed_at', 'created_at', 'updated_at']
    date_hierarchy  = 'date'
