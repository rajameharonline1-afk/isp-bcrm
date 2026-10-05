# ফাইল: backend/apps/income/serializers.py
from rest_framework import serializers
from .models import IncomeCategory, Income


class IncomeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = IncomeCategory
        fields = '__all__'


class IncomeListSerializer(serializers.ModelSerializer):
    category_name   = serializers.CharField(source='category.name', read_only=True)
    collected_by_name = serializers.CharField(source='collected_by.get_full_name', read_only=True, default='')

    class Meta:
        model  = Income
        fields = ['id', 'category', 'category_name', 'amount', 'date', 'method',
                  'reference_no', 'description', 'collected_by_name', 'created_at']


class IncomeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Income
        exclude = ['journal_entry', 'collected_by', 'created_at', 'updated_at']
