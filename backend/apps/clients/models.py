# ফাইল: backend/apps/clients/models.py
# এই ফাইলটি ISP-BCRM সিস্টেমের সম্পূর্ণ Client model ধারণ করে।
# claude.md-এ উল্লিখিত সব field এখানে সংজ্ঞায়িত করা হয়েছে।

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.accounts.models import User
from apps.servers.models import EncryptedField
from utils.validators import validate_bd_phone, validate_nid, validate_ip_address, validate_mac_address


class Client(models.Model):
    """
    ISP Client-এর সম্পূর্ণ তথ্য model।
    PPPoE credentials, billing, optical fiber, ONU সহ সব তথ্য এক জায়গায়।
    """

    class Status(models.TextChoices):
        ACTIVE      = 'active',      'Active'
        EXPIRED     = 'expired',     'Expired'
        SUSPENDED   = 'suspended',   'Suspended'
        DISCONNECTED= 'disconnected','Disconnected'
        LEFT        = 'left',        'Left/Cancelled'

    class PaymentStatus(models.TextChoices):
        PAID    = 'paid',    'Paid'
        UNPAID  = 'unpaid',  'Unpaid'
        PARTIAL = 'partial', 'Partial'
        OVERDUE = 'overdue', 'Overdue'

    # =============================================
    # ব্যক্তিগত তথ্য (Personal Information)
    # =============================================
    full_name   = models.CharField(max_length=150, verbose_name='Full Name')
    father_name = models.CharField(max_length=150, blank=True, verbose_name="Father's Name")
    phone       = models.CharField(max_length=20, validators=[validate_bd_phone], verbose_name='Phone Number', db_index=True)
    alt_phone   = models.CharField(max_length=20, blank=True, validators=[validate_bd_phone], verbose_name='Alternate Phone')
    email       = models.EmailField(blank=True, verbose_name='Email Address')
    nid         = models.CharField(max_length=20, blank=True, validators=[validate_nid], verbose_name='NID Number')

    # =============================================
    # ঠিকানা (Address)
    # =============================================
    house_name = models.CharField(max_length=150, blank=True, verbose_name='House/Building Name')
    house_no   = models.CharField(max_length=30, blank=True, verbose_name='House No.')
    road_no    = models.CharField(max_length=50, blank=True, verbose_name='Road/Street No.')
    address    = models.TextField(blank=True, verbose_name='Full Address')
    thana      = models.ForeignKey('configuration.Upazila', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Thana/Upazila')
    district   = models.ForeignKey('configuration.District', on_delete=models.SET_NULL, null=True, blank=True, verbose_name='District')
    zone       = models.ForeignKey('configuration.Zone', on_delete=models.SET_NULL, null=True, blank=True, related_name='clients')
    subzone    = models.ForeignKey('configuration.SubZone', on_delete=models.SET_NULL, null=True, blank=True, related_name='clients')
    box        = models.ForeignKey('configuration.Box', on_delete=models.SET_NULL, null=True, blank=True, related_name='clients')
    map_lat    = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='Map Latitude')
    map_lng    = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='Map Longitude')

    # =============================================
    # Connection তথ্য (Connection Details)
    # =============================================
    client_type  = models.ForeignKey('configuration.ClientType', on_delete=models.SET_NULL, null=True, blank=True)
    protocol     = models.ForeignKey('configuration.ProtocolType', on_delete=models.SET_NULL, null=True, blank=True)
    package      = models.ForeignKey('configuration.Package', on_delete=models.SET_NULL, null=True, blank=True, related_name='clients')
    package_no   = models.CharField(max_length=50, blank=True, verbose_name='Package No/Code')

    # PPPoE Credentials
    username     = models.CharField(max_length=64, unique=True, db_index=True, verbose_name='PPPoE Username')
    password     = EncryptedField(verbose_name='PPPoE Password (Encrypted)')
    ip_address   = models.GenericIPAddressField(null=True, blank=True, validators=[validate_ip_address])
    mac_address  = models.CharField(max_length=20, blank=True, validators=[validate_mac_address])

    # Router & Profile
    router       = models.ForeignKey('servers.MikrotikRouter', on_delete=models.SET_NULL, null=True, blank=True, related_name='clients')
    pppoe_profile = models.CharField(max_length=100, blank=True, verbose_name='PPPoE Profile Name')

    # =============================================
    # Billing তথ্য (Billing Information)
    # =============================================
    bill_date            = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        verbose_name='Bill Day of Month (1-31)'
    )
    expiry_day           = models.PositiveSmallIntegerField(default=30, verbose_name='Expiry Days After Bill Date')
    billing_start_month  = models.DateField(null=True, blank=True, verbose_name='Billing Start Month')
    connection_date      = models.DateField(default=timezone.now, verbose_name='Connection Date')
    expiry_date          = models.DateField(null=True, blank=True, verbose_name='Current Expiry Date')

    monthly_bill         = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Monthly Bill (BDT)')
    discount             = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Discount (BDT)')
    due_amount           = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Due Amount (BDT)')
    advance_balance      = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Advance Balance (BDT)')

    # =============================================
    # Status
    # =============================================
    status        = models.CharField(max_length=15, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    payment_status = models.CharField(max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)
    is_renewed    = models.BooleanField(default=False, verbose_name='Is Renewed This Month')
    renewed_at    = models.DateTimeField(null=True, blank=True)

    # =============================================
    # ছবি ও ডকুমেন্ট (Photos & Documents)
    # =============================================
    photo        = models.ImageField(upload_to='clients/photos/', blank=True, null=True)
    nid_photo    = models.ImageField(upload_to='clients/nid/', blank=True, null=True, verbose_name='NID Photo')
    reg_form_pic = models.ImageField(upload_to='clients/reg_forms/', blank=True, null=True, verbose_name='Registration Form Photo')

    # =============================================
    # Mobile App তথ্য (Mobile App Access)
    # =============================================
    app_enabled       = models.BooleanField(default=False, verbose_name='Mobile App Enabled')
    app_password      = models.CharField(max_length=64, blank=True, verbose_name='App Login Password')
    app_last_seen     = models.DateTimeField(null=True, blank=True, verbose_name='App Last Seen')
    app_registered_on = models.DateTimeField(null=True, blank=True, verbose_name='App Registration Date')

    # =============================================
    # Hardware / Optical Fiber তথ্য
    # =============================================
    device             = models.CharField(max_length=100, blank=True, verbose_name='Device Type/Model')
    optical_fiber      = models.BooleanField(default=True, verbose_name='Optical Fiber Connection')
    cable_meter        = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name='Cable Length (meters)')
    vendor             = models.CharField(max_length=100, blank=True, verbose_name='Hardware Vendor')
    serial_no          = models.CharField(max_length=64, blank=True, verbose_name='ONU/ONT Serial Number')
    fiber_code         = models.CharField(max_length=50, blank=True, verbose_name='Fiber Code')
    color_of_cord      = models.CharField(max_length=50, blank=True, verbose_name='Color of Cord')
    device_purchase_date = models.DateField(null=True, blank=True, verbose_name='Device Purchase Date')

    # Remote Management
    remote_mgmt_ip    = models.GenericIPAddressField(null=True, blank=True, verbose_name='Remote Management IP')
    remote_admin_user = models.CharField(max_length=64, blank=True, verbose_name='Remote Admin Username')
    remote_admin_pass = EncryptedField(blank=True, verbose_name='Remote Admin Password (Encrypted)')

    # MAC Reseller তথ্য
    mac_reseller          = models.ForeignKey('mac_reseller.MACReseller', on_delete=models.SET_NULL, null=True, blank=True, related_name='clients')
    mac_reseller_exported = models.BooleanField(default=False, verbose_name='Exported to MAC Reseller')

    # =============================================
    # Meta তথ্য
    # =============================================
    notes      = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='clients_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'clients'
        verbose_name = 'Client'
        ordering     = ['-created_at']
        indexes      = [
            models.Index(fields=['status', 'expiry_date']),
            models.Index(fields=['zone', 'status']),
            models.Index(fields=['bill_date', 'status']),
        ]

    def __str__(self):
        return f"{self.full_name} | {self.username} | {self.phone}"

    @property
    def payable_amount(self):
        """প্রতি মাসে প্রকৃত পরিশোধযোগ্য পরিমাণ (bill - discount)।"""
        return max(0, self.monthly_bill - self.discount)

    @property
    def is_expired(self):
        """Client-এর connection মেয়াদ শেষ হয়েছে কিনা।"""
        if self.expiry_date:
            return timezone.now().date() > self.expiry_date
        return False

    @property
    def days_until_expiry(self):
        """Expiry date-র কত দিন বাকি আছে।"""
        if self.expiry_date:
            delta = self.expiry_date - timezone.now().date()
            return delta.days
        return None


class ClientStatusLog(models.Model):
    """
    Client-এর status পরিবর্তনের log।
    কে কখন কোন কারণে status পরিবর্তন করেছে সব এখানে।
    """

    class Action(models.TextChoices):
        ACTIVATED    = 'activated',    'Activated'
        SUSPENDED    = 'suspended',    'Suspended'
        DISCONNECTED = 'disconnected', 'Disconnected'
        RENEWED      = 'renewed',      'Renewed'
        EXPIRED      = 'expired',      'Auto Expired'
        LEFT         = 'left',         'Left/Cancelled'

    client      = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='status_logs')
    action      = models.CharField(max_length=20, choices=Action.choices)
    from_status = models.CharField(max_length=15)
    to_status   = models.CharField(max_length=15)
    reason      = models.TextField(blank=True)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table  = 'client_status_logs'
        ordering  = ['-created_at']
        verbose_name = 'Client Status Log'

    def __str__(self):
        return f"{self.client.username}: {self.from_status} → {self.to_status}"
