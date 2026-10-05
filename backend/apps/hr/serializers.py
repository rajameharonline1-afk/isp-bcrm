# ফাইল: backend/apps/hr/serializers.py
# HR & Payroll module-এর সব serializer।

from rest_framework import serializers
from .models import (
    Department, Position, Employee, Payhead,
    Payroll, Payslip, PayslipItem,
    Attendance, ResignRule, Resignation, Rejoin,
)


# =============================================
# Department & Position
# =============================================

class DepartmentSerializer(serializers.ModelSerializer):
    employee_count = serializers.SerializerMethodField()

    class Meta:
        model  = Department
        fields = ['id', 'name', 'description', 'is_active', 'employee_count', 'created_at']

    def get_employee_count(self, obj):
        return obj.employees.filter(status=Employee.Status.ACTIVE).count()


class PositionSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True, default='')

    class Meta:
        model  = Position
        fields = ['id', 'name', 'department', 'department_name', 'description', 'is_active', 'created_at']


# =============================================
# Employee
# =============================================

class EmployeeListSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True, default='')
    position_name   = serializers.CharField(source='position.name', read_only=True, default='')
    years_of_service = serializers.FloatField(read_only=True)

    class Meta:
        model  = Employee
        fields = [
            'id', 'employee_id', 'full_name', 'phone', 'email',
            'department_name', 'position_name', 'employment_type',
            'status', 'joining_date', 'basic_salary', 'years_of_service',
        ]


class EmployeeDetailSerializer(serializers.ModelSerializer):
    department_name  = serializers.CharField(source='department.name', read_only=True, default='')
    position_name    = serializers.CharField(source='position.name', read_only=True, default='')
    reporting_to_name = serializers.CharField(source='reporting_to.full_name', read_only=True, default='')
    years_of_service  = serializers.FloatField(read_only=True)

    class Meta:
        model   = Employee
        exclude = ['created_by']


class EmployeeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model   = Employee
        exclude = ['employee_id', 'created_by', 'created_at', 'updated_at']


# =============================================
# Payhead
# =============================================

class PayheadSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Payhead
        fields = '__all__'


# =============================================
# Payroll & Payslip
# =============================================

class PayslipItemSerializer(serializers.ModelSerializer):
    payhead_name = serializers.CharField(source='payhead.name', read_only=True)
    head_type    = serializers.CharField(source='payhead.head_type', read_only=True)

    class Meta:
        model  = PayslipItem
        fields = ['id', 'payhead', 'payhead_name', 'head_type', 'amount']


class PayslipSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id   = serializers.CharField(source='employee.employee_id', read_only=True)
    department    = serializers.CharField(source='employee.department.name', read_only=True, default='')
    items         = PayslipItemSerializer(many=True, read_only=True)

    class Meta:
        model  = Payslip
        fields = [
            'id', 'payroll', 'employee', 'employee_name', 'employee_id', 'department',
            'basic_salary', 'total_earning', 'total_deduction',
            'gross_salary', 'net_salary', 'bonus',
            'advance_deduction', 'loan_deduction',
            'working_days', 'present_days', 'absent_days', 'leave_days', 'overtime_hours',
            'is_paid', 'paid_at', 'note', 'items', 'created_at',
        ]


class PayrollListSerializer(serializers.ModelSerializer):
    total_gross    = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_net      = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    employee_count = serializers.IntegerField(read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default='')

    class Meta:
        model  = Payroll
        fields = [
            'id', 'month', 'title', 'status', 'total_gross', 'total_net',
            'employee_count', 'created_by_name', 'approved_at', 'disbursed_at', 'created_at',
        ]


class PayrollDetailSerializer(serializers.ModelSerializer):
    payslips    = PayslipSerializer(many=True, read_only=True)
    total_gross = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_net   = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    employee_count = serializers.IntegerField(read_only=True)

    class Meta:
        model  = Payroll
        fields = '__all__'


# =============================================
# Attendance
# =============================================

class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    working_hours = serializers.FloatField(read_only=True)

    class Meta:
        model  = Attendance
        fields = [
            'id', 'employee', 'employee_name', 'date', 'status',
            'check_in', 'check_out', 'working_hours',
            'overtime_hours', 'note', 'created_at',
        ]


class BulkAttendanceSerializer(serializers.Serializer):
    """একসাথে অনেক কর্মচারীর attendance mark করার জন্য।"""
    date    = serializers.DateField()
    records = serializers.ListField(
        child=serializers.DictField(),
        help_text='[{employee_id, status, check_in, check_out, overtime_hours}, ...]'
    )


# =============================================
# Resignation & Rejoin
# =============================================

class ResignRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ResignRule
        fields = '__all__'


class ResignationSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True, default='')

    class Meta:
        model  = Resignation
        fields = '__all__'
        read_only_fields = ['gratuity_amount', 'leave_encash', 'total_settlement',
                             'approved_by', 'approved_at']


class RejoinSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model  = Rejoin
        fields = '__all__'
        read_only_fields = ['created_at']
