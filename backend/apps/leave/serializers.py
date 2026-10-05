# ফাইল: backend/apps/leave/serializers.py
from rest_framework import serializers
from .models import LeaveCategory, LeaveSetup, LeaveBalance, LeaveApplication


class LeaveCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = LeaveCategory
        fields = '__all__'


class LeaveSetupSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model  = LeaveSetup
        fields = '__all__'


class LeaveBalanceSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    remaining     = serializers.IntegerField(read_only=True)

    class Meta:
        model  = LeaveBalance
        fields = ['id', 'employee', 'employee_name', 'category', 'category_name',
                  'fiscal_year', 'total_days', 'used_days', 'carry_forward_days',
                  'remaining', 'created_at', 'updated_at']


class LeaveApplicationListSerializer(serializers.ModelSerializer):
    employee_name  = serializers.CharField(source='employee.full_name', read_only=True)
    category_name  = serializers.CharField(source='category.name', read_only=True)
    category_color = serializers.CharField(source='category.color', read_only=True)

    class Meta:
        model  = LeaveApplication
        fields = ['id', 'employee', 'employee_name', 'category', 'category_name',
                  'category_color', 'start_date', 'end_date', 'total_days',
                  'reason', 'status', 'applied_at']


class LeaveApplicationDetailSerializer(serializers.ModelSerializer):
    employee_name    = serializers.CharField(source='employee.full_name', read_only=True)
    category_name    = serializers.CharField(source='category.name', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True, default='')

    class Meta:
        model  = LeaveApplication
        fields = '__all__'
        read_only_fields = ['total_days', 'reviewed_by', 'reviewed_at', 'applied_at']


class LeaveApprovalSerializer(serializers.Serializer):
    action      = serializers.ChoiceField(choices=['approve', 'reject'])
    review_note = serializers.CharField(required=False, default='', allow_blank=True)
