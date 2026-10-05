# ফাইল: backend/apps/configuration/models.py
# এই ফাইলটি ISP-BCRM সিস্টেমের সব মূল configuration/lookup table models ধারণ করে।

from django.db import models
from apps.accounts.models import User


class District(models.Model):
    """বাংলাদেশের জেলা তালিকা।"""
    name = models.CharField(max_length=100, unique=True, verbose_name='District Name')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'config_districts'
        verbose_name = 'District'
        ordering = ['name']

    def __str__(self):
        return self.name


class Upazila(models.Model):
    """বাংলাদেশের উপজেলা/থানা তালিকা।"""
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name='upazilas')
    name = models.CharField(max_length=100, verbose_name='Upazila/Thana Name')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'config_upazilas'
        verbose_name = 'Upazila'
        unique_together = ['district', 'name']
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.district.name})"


class Zone(models.Model):
    """ISP সার্ভিস এলাকার Zone (যেমন: North Zone, South Zone)।"""
    name = models.CharField(max_length=100, unique=True, verbose_name='Zone Name')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='zones_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'config_zones'
        verbose_name = 'Zone'
        ordering = ['name']

    def __str__(self):
        return self.name


class SubZone(models.Model):
    """Zone-এর অধীনে Sub Zone।"""
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='sub_zones')
    name = models.CharField(max_length=100, verbose_name='Sub Zone Name')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'config_sub_zones'
        verbose_name = 'Sub Zone'
        unique_together = ['zone', 'name']
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.zone.name})"


class Box(models.Model):
    """SubZone-এর অধীনে Distribution Box/Cabinet।"""
    sub_zone = models.ForeignKey(SubZone, on_delete=models.CASCADE, related_name='boxes')
    name = models.CharField(max_length=100, verbose_name='Box Name')
    location = models.TextField(blank=True, verbose_name='Box Location')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'config_boxes'
        verbose_name = 'Box'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.sub_zone.name})"


class Package(models.Model):
    """Internet Package তালিকা (যেমন: 5Mbps, 10Mbps, 20Mbps)।"""

    class PackageType(models.TextChoices):
        PPPOE = 'pppoe', 'PPPoE'
        STATIC = 'static', 'Static IP'
        HOTSPOT = 'hotspot', 'Hotspot'

    name = models.CharField(max_length=100, verbose_name='Package Name')
    package_type = models.CharField(max_length=20, choices=PackageType.choices, default=PackageType.PPPOE)

    # Speed limits
    download_speed = models.CharField(max_length=20, verbose_name='Download Speed (Mbps)')
    upload_speed = models.CharField(max_length=20, verbose_name='Upload Speed (Mbps)')

    # Billing
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Monthly Price (BDT)')
    description = models.TextField(blank=True)

    # Mikrotik PPPoE Profile name (Mikrotik-এ যে profile নামে তৈরি করা আছে)
    mikrotik_profile = models.CharField(max_length=100, blank=True, verbose_name='Mikrotik Profile Name')

    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='packages_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'config_packages'
        verbose_name = 'Package'
        ordering = ['monthly_price']

    def __str__(self):
        return f"{self.name} - {self.download_speed}/{self.upload_speed} - ৳{self.monthly_price}"


class ConnectionType(models.Model):
    """Connection type তালিকা (যেমন: Fiber, Cable, Wireless)।"""
    name = models.CharField(max_length=50, unique=True, verbose_name='Connection Type')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'config_connection_types'
        verbose_name = 'Connection Type'

    def __str__(self):
        return self.name


class ClientType(models.Model):
    """Client type তালিকা (যেমন: Home, Corporate, SME)।"""
    name = models.CharField(max_length=50, unique=True, verbose_name='Client Type')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'config_client_types'
        verbose_name = 'Client Type'

    def __str__(self):
        return self.name


class ProtocolType(models.Model):
    """Protocol type তালিকা (PPPoE, Static, DHCP)।"""
    name = models.CharField(max_length=50, unique=True, verbose_name='Protocol Type')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'config_protocol_types'
        verbose_name = 'Protocol Type'

    def __str__(self):
        return self.name


class BillingStatus(models.Model):
    """Billing status তালিকা (Active, Expired, Suspended, etc.)।"""
    name = models.CharField(max_length=50, unique=True, verbose_name='Billing Status')
    color_code = models.CharField(max_length=10, default='#000000', verbose_name='Color (Hex)')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'config_billing_statuses'
        verbose_name = 'Billing Status'

    def __str__(self):
        return self.name
