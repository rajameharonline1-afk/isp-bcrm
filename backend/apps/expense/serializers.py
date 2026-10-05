# ফাইল: backend/apps/expense/serializers.py
from rest_framework import serializers
from .models import ExpenseCategory, Expense


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = ExpenseCategory
        fields = '__all__'


class ExpenseListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True, default='')

    class Meta:
        model  = Expense
        fields = ['id', 'category', 'category_name', 'amount', 'date', 'method',
                  'reference_no', 'description', 'payee', 'recorded_by_name', 'created_at']


class ExpenseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Expense
        exclude = ['journal_entry', 'recorded_by', 'approved_by', 'created_at', 'updated_at']
