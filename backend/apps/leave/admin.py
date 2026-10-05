# ফাইল: backend/apps/leave/admin.py
from django.contrib import admin
from .models import LeaveCategory, LeaveSetup, LeaveBalance, LeaveApplication


@admin.register(LeaveCategory)
class LeaveCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'short_code', 'is_paid', 'is_active']
    list_filter  = ['is_paid', 'is_active']


@admin.register(LeaveSetup)
class LeaveSetupAdmin(admin.ModelAdmin):
    list_display = ['category', 'employment_type', 'days_per_year', 'carry_forward', 'fiscal_year']
    list_filter  = ['fiscal_year', 'employment_type']


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display  = ['employee', 'category', 'total_days', 'used_days', 'fiscal_year']
    list_filter   = ['fiscal_year', 'category']
    raw_id_fields = ['employee']
    search_fields = ['employee__full_name']


@admin.register(LeaveApplication)
class LeaveApplicationAdmin(admin.ModelAdmin):
    list_display  = ['employee', 'category', 'start_date', 'end_date', 'total_days', 'status']
    list_filter   = ['status', 'category']
    search_fields = ['employee__full_name']
    raw_id_fields = ['employee', 'reviewed_by']
    date_hierarchy = 'start_date'
