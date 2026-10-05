# ফাইল: backend/apps/daily_account/serializers.py
from rest_framework import serializers
from .models import DailyAccount


class DailyAccountSerializer(serializers.ModelSerializer):
    closed_by_name = serializers.CharField(source='closed_by.get_full_name', read_only=True, default='')

    class Meta:
        model  = DailyAccount
        fields = '__all__'
        read_only_fields = ['closed_by', 'closed_at', 'created_at', 'updated_at']
