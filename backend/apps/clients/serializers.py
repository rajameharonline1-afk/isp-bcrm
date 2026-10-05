# ফাইল: backend/apps/clients/serializers.py
# Client API-এর সব serializer এখানে সংজ্ঞায়িত করা হয়েছে।

from rest_framework import serializers
from .models import Client, ClientStatusLog


class ClientListSerializer(serializers.ModelSerializer):
    """Client list-এর জন্য সংক্ষিপ্ত serializer।"""
    zone_name     = serializers.CharField(source='zone.name', read_only=True, default='')
    package_name  = serializers.CharField(source='package.name', read_only=True, default='')
    router_name   = serializers.CharField(source='router.name', read_only=True, default='')
    payable_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)

    class Meta:
        model  = Client
        fields = [
            'id', 'full_name', 'username', 'phone', 'status', 'payment_status',
            'package_name', 'zone_name', 'router_name', 'monthly_bill', 'discount',
            'payable_amount', 'due_amount', 'advance_balance',
            'expiry_date', 'days_until_expiry', 'connection_date', 'created_at',
        ]


class ClientDetailSerializer(serializers.ModelSerializer):
    """Client detail view-এর জন্য সম্পূর্ণ serializer।"""
    zone_name     = serializers.CharField(source='zone.name', read_only=True, default='')
    subzone_name  = serializers.CharField(source='subzone.name', read_only=True, default='')
    box_name      = serializers.CharField(source='box.name', read_only=True, default='')
    thana_name    = serializers.CharField(source='thana.name', read_only=True, default='')
    district_name = serializers.CharField(source='district.name', read_only=True, default='')
    package_name  = serializers.CharField(source='package.name', read_only=True, default='')
    router_name   = serializers.CharField(source='router.name', read_only=True, default='')
    client_type_name = serializers.CharField(source='client_type.name', read_only=True, default='')
    protocol_name = serializers.CharField(source='protocol.name', read_only=True, default='')
    payable_amount    = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    days_until_expiry = serializers.IntegerField(read_only=True)
    is_expired        = serializers.BooleanField(read_only=True)
    created_by_name   = serializers.CharField(source='created_by.get_full_name', read_only=True, default='')

    class Meta:
        model  = Client
        exclude = ['password', 'remote_admin_pass']  # Encrypted passwords API-তে expose করা হবে না


class ClientCreateSerializer(serializers.ModelSerializer):
    """নতুন Client তৈরির জন্য serializer।"""
    sync_mikrotik = serializers.BooleanField(default=True, write_only=True)
    sync_radius   = serializers.BooleanField(default=True, write_only=True)

    class Meta:
        model  = Client
        exclude = ['created_by', 'created_at', 'updated_at', 'is_renewed', 'renewed_at',
                   'payment_status', 'app_last_seen', 'app_registered_on',
                   'mac_reseller_exported']
        extra_kwargs = {
            'password':          {'write_only': True},
            'remote_admin_pass': {'write_only': True},
            'app_password':      {'write_only': True},
        }

    def validate_username(self, value):
        """Username unique কিনা check করা।"""
        if Client.objects.filter(username=value).exists():
            raise serializers.ValidationError("This PPPoE username is already taken.")
        return value

    def validate_bill_date(self, value):
        if not 1 <= value <= 31:
            raise serializers.ValidationError("Bill date must be between 1 and 31.")
        return value


class ClientUpdateSerializer(serializers.ModelSerializer):
    """Client তথ্য আপডেটের জন্য serializer (credential ছাড়া)।"""

    class Meta:
        model  = Client
        exclude = ['username', 'password', 'remote_admin_pass', 'created_by',
                   'created_at', 'updated_at', 'is_renewed', 'renewed_at',
                   'payment_status', 'app_last_seen', 'app_registered_on']


class ClientPasswordChangeSerializer(serializers.Serializer):
    """Client PPPoE password পরিবর্তনের জন্য serializer।"""
    new_password    = serializers.CharField(min_length=6, max_length=64, write_only=True)
    sync_mikrotik   = serializers.BooleanField(default=True)
    sync_radius     = serializers.BooleanField(default=True)


class ClientRenewSerializer(serializers.Serializer):
    """Client renewal-এর জন্য serializer।"""
    months       = serializers.IntegerField(min_value=1, max_value=12, default=1)
    advance_used = serializers.DecimalField(max_digits=10, decimal_places=2, default=0)


class ClientPackageChangeSerializer(serializers.Serializer):
    """Client package পরিবর্তনের জন্য serializer।"""
    package_id = serializers.IntegerField()


class ClientStatusLogSerializer(serializers.ModelSerializer):
    """Client status change log-এর serializer।"""
    performed_by_name = serializers.CharField(source='performed_by.get_full_name', read_only=True, default='System')

    class Meta:
        model  = ClientStatusLog
        fields = ['id', 'action', 'from_status', 'to_status', 'reason',
                  'performed_by_name', 'created_at']
