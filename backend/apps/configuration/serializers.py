# ফাইল: backend/apps/configuration/serializers.py
# এই ফাইলটি configuration models-এর সব serializers ধারণ করে।

from rest_framework import serializers
from .models import District, Upazila, Zone, SubZone, Box, Package, ConnectionType, ClientType, ProtocolType, BillingStatus


class DistrictSerializer(serializers.ModelSerializer):
    class Meta:
        model = District
        fields = ['id', 'name', 'is_active', 'created_at']


class UpazilaSerializer(serializers.ModelSerializer):
    district_name = serializers.CharField(source='district.name', read_only=True)

    class Meta:
        model = Upazila
        fields = ['id', 'district', 'district_name', 'name', 'is_active', 'created_at']


class BoxSerializer(serializers.ModelSerializer):
    sub_zone_name = serializers.CharField(source='sub_zone.name', read_only=True)
    zone_name = serializers.CharField(source='sub_zone.zone.name', read_only=True)

    class Meta:
        model = Box
        fields = ['id', 'sub_zone', 'sub_zone_name', 'zone_name', 'name', 'location',
                  'latitude', 'longitude', 'is_active', 'created_at']


class SubZoneSerializer(serializers.ModelSerializer):
    zone_name = serializers.CharField(source='zone.name', read_only=True)
    boxes = BoxSerializer(many=True, read_only=True)

    class Meta:
        model = SubZone
        fields = ['id', 'zone', 'zone_name', 'name', 'description', 'is_active', 'created_at', 'boxes']


class ZoneSerializer(serializers.ModelSerializer):
    sub_zones = SubZoneSerializer(many=True, read_only=True)

    class Meta:
        model = Zone
        fields = ['id', 'name', 'description', 'is_active', 'created_at', 'updated_at', 'sub_zones']


class ZoneListSerializer(serializers.ModelSerializer):
    """Zone list-এর জন্য lightweight serializer (sub_zones ছাড়া)।"""
    class Meta:
        model = Zone
        fields = ['id', 'name', 'description', 'is_active', 'created_at']


class PackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Package
        fields = [
            'id', 'name', 'package_type', 'download_speed', 'upload_speed',
            'monthly_price', 'description', 'mikrotik_profile', 'is_active',
            'created_at', 'updated_at'
        ]


class ConnectionTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConnectionType
        fields = ['id', 'name', 'is_active']


class ClientTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientType
        fields = ['id', 'name', 'is_active']


class ProtocolTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProtocolType
        fields = ['id', 'name', 'is_active']


class BillingStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingStatus
        fields = ['id', 'name', 'color_code', 'is_active']
