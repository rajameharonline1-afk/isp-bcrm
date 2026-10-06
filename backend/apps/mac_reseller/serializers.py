# ফাইল: backend/apps/mac_reseller/serializers.py
# এই ফাইলটি MAC Reseller সংক্রান্ত সব API serializer ধারণ করে।

from rest_framework import serializers
from django.utils import timezone
from .models import (
    MACReseller, MACResellerPackage, MACResellerTariffConfig,
    MACResellerFunding, ClientPGWPayment, PGWTransactionSettlement,
    MACResellerNotice,
)


# ─────────────────────────────────────────────
#  MAC Reseller
# ─────────────────────────────────────────────

class MACResellerListSerializer(serializers.ModelSerializer):
    """Reseller তালিকার সংক্ষিপ্ত serializer।"""
    client_count = serializers.IntegerField(source='clients.count', read_only=True)

    class Meta:
        model  = MACReseller
        fields = [
            'id', 'name', 'contact', 'email', 'address',
            'balance', 'status', 'client_count', 'created_at',
        ]


class MACResellerDetailSerializer(serializers.ModelSerializer):
    """Reseller বিস্তারিত তথ্যের serializer।"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default='')
    client_count    = serializers.IntegerField(source='clients.count', read_only=True)

    class Meta:
        model  = MACReseller
        fields = '__all__'
        read_only_fields = ['balance', 'created_by', 'created_at', 'updated_at']


class MACResellerCreateUpdateSerializer(serializers.ModelSerializer):
    """Reseller তৈরি ও আপডেটের serializer।"""

    class Meta:
        model  = MACReseller
        fields = ['name', 'contact', 'email', 'address', 'status']

    def validate_name(self, value):
        """Reseller নাম unique কিনা যাচাই।"""
        qs = MACReseller.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("এই নামে একটি Reseller ইতিমধ্যে আছে।")
        return value


# ─────────────────────────────────────────────
#  MAC Reseller Package
# ─────────────────────────────────────────────

class MACResellerPackageSerializer(serializers.ModelSerializer):
    """Reseller প্যাকেজের serializer।"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default='')

    class Meta:
        model  = MACResellerPackage
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def validate(self, data):
        """Bandwidth মান শূন্যের বেশি হতে হবে।"""
        if data.get('bandwidth_down', 0) <= 0 or data.get('bandwidth_up', 0) <= 0:
            raise serializers.ValidationError("Bandwidth অবশ্যই ০-এর বেশি হতে হবে।")
        return data


# ─────────────────────────────────────────────
#  Tariff Config
# ─────────────────────────────────────────────

class TariffConfigListSerializer(serializers.ModelSerializer):
    """Tariff config তালিকার serializer।"""
    reseller_name  = serializers.CharField(source='reseller.name', read_only=True)
    package_name   = serializers.CharField(source='package.name', read_only=True)
    profit_margin  = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model  = MACResellerTariffConfig
        fields = [
            'id', 'reseller', 'reseller_name', 'package', 'package_name',
            'reseller_price', 'max_retail_price', 'profit_margin',
            'effective_from', 'is_active',
        ]


class TariffConfigCreateUpdateSerializer(serializers.ModelSerializer):
    """Tariff config তৈরি ও আপডেটের serializer।"""

    class Meta:
        model  = MACResellerTariffConfig
        fields = [
            'reseller', 'package', 'reseller_price',
            'max_retail_price', 'effective_from', 'is_active',
        ]

    def validate(self, data):
        """Reseller মূল্য সর্বোচ্চ retail মূল্যের চেয়ে কম হতে হবে।"""
        if data.get('reseller_price', 0) >= data.get('max_retail_price', 0):
            raise serializers.ValidationError(
                "Reseller price অবশ্যই max retail price-এর কম হতে হবে।"
            )
        return data


# ─────────────────────────────────────────────
#  MAC Reseller Funding
# ─────────────────────────────────────────────

class FundingListSerializer(serializers.ModelSerializer):
    """Funding তালিকার serializer।"""
    reseller_name  = serializers.CharField(source='reseller.name', read_only=True)
    funded_by_name = serializers.CharField(source='funded_by.get_full_name', read_only=True, default='')
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True, default='')

    class Meta:
        model  = MACResellerFunding
        fields = [
            'id', 'reseller', 'reseller_name', 'amount', 'payment_method',
            'transaction_id', 'status', 'balance_before', 'balance_after',
            'funded_by_name', 'approved_by_name', 'approved_at', 'funded_at',
        ]


class FundingCreateSerializer(serializers.ModelSerializer):
    """নতুন funding request তৈরির serializer।"""

    class Meta:
        model  = MACResellerFunding
        fields = ['reseller', 'amount', 'payment_method', 'transaction_id', 'note']

    def validate_amount(self, value):
        """Funding amount ধনাত্মক হতে হবে।"""
        if value <= 0:
            raise serializers.ValidationError("Funding amount ০-এর বেশি হতে হবে।")
        return value


class FundingApproveSerializer(serializers.Serializer):
    """Funding approve/reject-এর serializer।"""
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    note   = serializers.CharField(max_length=500, required=False, allow_blank=True)


# ─────────────────────────────────────────────
#  Client PGW Payment
# ─────────────────────────────────────────────

class ClientPGWPaymentListSerializer(serializers.ModelSerializer):
    """PGW payment তালিকার serializer।"""
    client_name    = serializers.CharField(source='client.full_name', read_only=True)
    client_username = serializers.CharField(source='client.username', read_only=True)
    reseller_name  = serializers.CharField(source='reseller.name', read_only=True, default='')
    net_amount     = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model  = ClientPGWPayment
        fields = [
            'id', 'client', 'client_name', 'client_username',
            'reseller', 'reseller_name', 'billing',
            'amount', 'processing_fee', 'net_amount',
            'gateway', 'pgw_transaction_id', 'order_id',
            'status', 'payment_date', 'created_at',
        ]


class ClientPGWPaymentDetailSerializer(serializers.ModelSerializer):
    """PGW payment বিস্তারিত serializer।"""
    client_name  = serializers.CharField(source='client.full_name', read_only=True)
    reseller_name = serializers.CharField(source='reseller.name', read_only=True, default='')
    net_amount   = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model  = ClientPGWPayment
        fields = '__all__'


class PGWPaymentStatusUpdateSerializer(serializers.Serializer):
    """PGW payment status আপডেটের serializer (webhook callback)।"""
    order_id           = serializers.CharField(max_length=100)
    pgw_transaction_id = serializers.CharField(max_length=200)
    status             = serializers.ChoiceField(choices=ClientPGWPayment.PGWStatus.choices)
    gateway_response   = serializers.JSONField(required=False, default=dict)


# ─────────────────────────────────────────────
#  PGW Transaction Settlement
# ─────────────────────────────────────────────

class SettlementListSerializer(serializers.ModelSerializer):
    """Settlement তালিকার serializer।"""
    reseller_name  = serializers.CharField(source='reseller.name', read_only=True)
    settled_by_name = serializers.CharField(source='settled_by.get_full_name', read_only=True, default='')

    class Meta:
        model  = PGWTransactionSettlement
        fields = [
            'id', 'reseller', 'reseller_name', 'payment_count',
            'total_amount', 'total_fee', 'net_settlement',
            'settlement_date', 'status', 'settled_by_name', 'settled_at', 'created_at',
        ]


class SettlementDetailSerializer(serializers.ModelSerializer):
    """Settlement বিস্তারিত serializer।"""
    reseller_name  = serializers.CharField(source='reseller.name', read_only=True)
    settled_by_name = serializers.CharField(source='settled_by.get_full_name', read_only=True, default='')
    payments       = ClientPGWPaymentListSerializer(many=True, read_only=True)

    class Meta:
        model  = PGWTransactionSettlement
        fields = '__all__'


class SettlementCreateSerializer(serializers.Serializer):
    """নতুন settlement তৈরির serializer।"""
    reseller_id     = serializers.IntegerField()
    # কোন payment IDs এই settlement-এ include হবে
    payment_ids     = serializers.ListField(
        child=serializers.IntegerField(), min_length=1
    )
    settlement_date = serializers.DateField()
    note            = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')

    def validate_reseller_id(self, value):
        if not MACReseller.objects.filter(pk=value).exists():
            raise serializers.ValidationError("এই ID-র কোনো Reseller পাওয়া যায়নি।")
        return value

    def validate_payment_ids(self, value):
        """Payment IDs অবশ্যই success status-এর হতে হবে।"""
        invalid = ClientPGWPayment.objects.filter(
            pk__in=value
        ).exclude(status=ClientPGWPayment.PGWStatus.SUCCESS).count()
        if invalid:
            raise serializers.ValidationError(
                f"{invalid}টি payment 'success' অবস্থায় নেই, settlement সম্ভব না।"
            )
        return value


# ─────────────────────────────────────────────
#  MAC Reseller Notice
# ─────────────────────────────────────────────

class NoticeListSerializer(serializers.ModelSerializer):
    """Notice তালিকার serializer।"""
    created_by_name   = serializers.CharField(source='created_by.get_full_name', read_only=True, default='')
    target_count      = serializers.IntegerField(source='target_resellers.count', read_only=True)
    is_expired        = serializers.SerializerMethodField()

    class Meta:
        model  = MACResellerNotice
        fields = [
            'id', 'title', 'notice_type', 'is_active',
            'publish_at', 'expire_at', 'is_expired',
            'target_count', 'created_by_name', 'created_at',
        ]

    def get_is_expired(self, obj):
        """Notice মেয়াদ শেষ হয়েছে কিনা।"""
        if obj.expire_at and obj.expire_at < timezone.now():
            return True
        return False


class NoticeDetailSerializer(serializers.ModelSerializer):
    """Notice বিস্তারিত serializer।"""
    created_by_name  = serializers.CharField(source='created_by.get_full_name', read_only=True, default='')
    target_resellers = serializers.PrimaryKeyRelatedField(
        queryset=MACReseller.objects.all(), many=True, required=False
    )

    class Meta:
        model  = MACResellerNotice
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at', 'updated_at']

    def validate(self, data):
        """Publish তারিখ Expire তারিখের আগে হতে হবে।"""
        if data.get('expire_at') and data.get('publish_at'):
            if data['expire_at'] <= data['publish_at']:
                raise serializers.ValidationError("Expire তারিখ অবশ্যই Publish তারিখের পরে হতে হবে।")
        return data
