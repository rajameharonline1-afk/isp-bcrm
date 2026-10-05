# ফাইল: backend/apps/billing/serializers.py
# Billing ও Payment API-এর serializers।

from rest_framework import serializers
from .models import Billing, Payment


class BillingListSerializer(serializers.ModelSerializer):
    """Billing list-এর সংক্ষিপ্ত serializer।"""
    client_name    = serializers.CharField(source='client.full_name', read_only=True)
    client_username = serializers.CharField(source='client.username', read_only=True)
    remaining_due  = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model  = Billing
        fields = [
            'id', 'client', 'client_name', 'client_username',
            'bill_month', 'bill_amount', 'discount', 'payable_amount',
            'paid_amount', 'due_amount', 'advance_used', 'status',
            'bill_date', 'due_date', 'remaining_due', 'created_at',
        ]


class BillingDetailSerializer(serializers.ModelSerializer):
    """Billing detail view serializer।"""
    client_name     = serializers.CharField(source='client.full_name', read_only=True)
    client_username = serializers.CharField(source='client.username', read_only=True)
    client_phone    = serializers.CharField(source='client.phone', read_only=True)
    remaining_due   = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    payments        = serializers.SerializerMethodField()
    generated_by_name = serializers.CharField(source='generated_by.get_full_name', read_only=True, default='Auto')

    class Meta:
        model  = Billing
        fields = '__all__'

    def get_payments(self, obj):
        return PaymentListSerializer(obj.payments.all(), many=True).data


class PaymentListSerializer(serializers.ModelSerializer):
    """Payment list serializer।"""
    collected_by_name = serializers.CharField(source='collected_by.get_full_name', read_only=True, default='')

    class Meta:
        model  = Payment
        fields = [
            'id', 'client', 'billing', 'amount', 'method',
            'transaction_id', 'collected_by_name', 'note',
            'payment_date', 'created_at',
        ]


class PaymentCreateSerializer(serializers.Serializer):
    """Payment collection-এর জন্য serializer।"""
    client_id      = serializers.IntegerField()
    billing_id     = serializers.IntegerField(required=False, allow_null=True)
    amount         = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=1)
    method         = serializers.ChoiceField(choices=Payment.PaymentMethod.choices)
    transaction_id = serializers.CharField(max_length=100, required=False, default='', allow_blank=True)
    note           = serializers.CharField(required=False, default='', allow_blank=True)
    use_advance    = serializers.BooleanField(default=False,
                         help_text='Client-এর advance balance থেকে payment apply করা')


class BillGenerateSerializer(serializers.Serializer):
    """Manual bill generation-এর জন্য serializer।"""
    client_id  = serializers.IntegerField()
    bill_month = serializers.DateField(help_text='YYYY-MM-01 format')
