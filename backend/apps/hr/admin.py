# ফাইল: backend/apps/hr/admin.py
from django.contrib import admin
from .models import (
    Department, Position, Employee, Payhead,
    Payroll, Payslip, PayslipItem,
    Attendance, ResignRule, Resignation, Rejoin,
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display  = ['name', 'is_active', 'created_at']
    list_filter   = ['is_active']
    search_fields = ['name']


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display  = ['name', 'department', 'is_active']
    list_filter   = ['department', 'is_active']
    search_fields = ['name']


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display  = ['employee_id', 'full_name', 'phone', 'department',
                     'position', 'status', 'joining_date', 'basic_salary']
    list_filter   = ['status', 'department', 'employment_type']
    search_fields = ['full_name', 'employee_id', 'phone', 'nid']
    readonly_fields = ['employee_id', 'created_at', 'updated_at']
    raw_id_fields   = ['user', 'department', 'position', 'reporting_to', 'created_by']


class PayslipItemInline(admin.TabularInline):
    model = PayslipItem
    extra = 0


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display  = ['employee', 'payroll', 'basic_salary', 'gross_salary', 'net_salary', 'is_paid']
    list_filter   = ['payroll__month', 'is_paid']
    search_fields = ['employee__full_name', 'employee__employee_id']
    inlines       = [PayslipItemInline]
    raw_id_fields = ['employee', 'payroll']


@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display  = ['month', 'title', 'status', 'employee_count', 'total_net', 'created_at']
    list_filter   = ['status']


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display  = ['employee', 'date', 'status', 'check_in', 'check_out', 'overtime_hours']
    list_filter   = ['status', 'date']
    search_fields = ['employee__full_name', 'employee__employee_id']
    date_hierarchy = 'date'


@admin.register(ResignRule)
class ResignRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'notice_days', 'gratuity_applicable', 'is_active']


@admin.register(Resignation)
class ResignationAdmin(admin.ModelAdmin):
    list_display  = ['employee', 'resign_type', 'apply_date', 'last_working_date', 'status']
    list_filter   = ['status', 'resign_type']
    search_fields = ['employee__full_name']


@admin.register(Rejoin)
class RejoinAdmin(admin.ModelAdmin):
    list_display = ['employee', 'rejoin_date', 'department', 'position', 'new_basic_salary']
    search_fields = ['employee__full_name']
