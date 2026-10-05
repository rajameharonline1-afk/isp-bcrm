# ফাইল: backend/apps/olt/models.py
# এই ফাইলটি OLT device, ONU inventory, signal monitoring এবং event log-এর সব database model ধারণ করে।

from django.db import models
from django.utils import timezone
from apps.accounts.models import User
from apps.servers.models import EncryptedField


class OLT(models.Model):
    """
    OLT (Optical Line Terminal) device-এর তথ্য।
    SNMP polling এবং SSH CLI automation-এর জন্য সব credentials এখানে।
    """

    class Vendor(models.TextChoices):
        HUAWEI    = 'huawei',     'Huawei'
        ZTE       = 'zte',        'ZTE'
        FIBERHOME = 'fiberhome',  'FiberHome'
        BDCOM     = 'bdcom',      'BDCOM'
        CALIX     = 'calix',      'Calix'
        OTHER     = 'other',      'Other'

    class OLTStatus(models.TextChoices):
        ONLINE  = 'online',  'Online'
        OFFLINE = 'offline', 'Offline'
        UNKNOWN = 'unknown', 'Unknown'

    class SNMPVersion(models.TextChoices):
        V1  = 'v1',  'SNMPv1'
        V2C = 'v2c', 'SNMPv2c'
        V3  = 'v3',  'SNMPv3'

    # OLT মূল তথ্য
    name        = models.CharField(max_length=100, verbose_name='OLT Name')
    ip_address  = models.GenericIPAddressField(verbose_name='Management IP')
    vendor      = models.CharField(max_length=20, choices=Vendor.choices, default=Vendor.HUAWEI)
    model       = models.CharField(max_length=100, blank=True, verbose_name='Model (e.g. MA5600T)')
    description = models.TextField(blank=True)

    # SSH / Telnet CLI credentials
    ssh_port     = models.PositiveIntegerField(default=22)
    ssh_username = models.CharField(max_length=100, blank=True)
    ssh_password = EncryptedField(blank=True, verbose_name='SSH Password (Encrypted)')
    enable_password = EncryptedField(blank=True, verbose_name='Enable/Super Password (Encrypted)')
    use_telnet   = models.BooleanField(default=False, verbose_name='Use Telnet instead of SSH')
    telnet_port  = models.PositiveIntegerField(default=23)

    # SNMP configuration (ONU RX power polling-এর জন্য)
    snmp_version   = models.CharField(max_length=5, choices=SNMPVersion.choices, default=SNMPVersion.V2C)
    snmp_community = EncryptedField(default='public', verbose_name='SNMP Community (Encrypted)')
    snmp_port      = models.PositiveIntegerField(default=161)
    snmp_timeout   = models.PositiveIntegerField(default=10, verbose_name='SNMP Timeout (seconds)')
    snmp_retries   = models.PositiveIntegerField(default=2)

    # SNMPv3 credentials (v3 হলে ব্যবহার হবে)
    snmp_v3_username   = models.CharField(max_length=64, blank=True)
    snmp_v3_auth_key   = EncryptedField(blank=True)
    snmp_v3_priv_key   = EncryptedField(blank=True)
    snmp_v3_auth_proto = models.CharField(max_length=10, default='SHA', blank=True)
    snmp_v3_priv_proto = models.CharField(max_length=10, default='AES', blank=True)

    # Zone সংযোগ
    zone = models.ForeignKey(
        'configuration.Zone',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='olts'
    )

    # Status tracking
    status       = models.CharField(max_length=10, choices=OLTStatus.choices, default=OLTStatus.UNKNOWN)
    last_polled  = models.DateTimeField(null=True, blank=True, verbose_name='Last SNMP Poll Time')
    total_onus   = models.PositiveIntegerField(default=0, verbose_name='Total ONUs (cached)')
    online_onus  = models.PositiveIntegerField(default=0, verbose_name='Online ONUs (cached)')

    is_active  = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table  = 'olt_devices'
        verbose_name = 'OLT Device'
        ordering  = ['name']

    def __str__(self):
        return f"{self.name} ({self.ip_address}) [{self.get_vendor_display()}]"


class OLTPort(models.Model):
    """
    OLT-এর প্রতিটি PON port-এর তথ্য।
    Frame/Slot/Port structure অনুযায়ী organize করা।
    """

    class PortType(models.TextChoices):
        GPON  = 'gpon',  'GPON'
        EPON  = 'epon',  'EPON'
        XGPON = 'xgpon', 'XG-PON'
        XGSPON= 'xgspon','XGS-PON'

    olt       = models.ForeignKey(OLT, on_delete=models.CASCADE, related_name='ports')
    port_type = models.CharField(max_length=10, choices=PortType.choices, default=PortType.GPON)

    # Huawei: frame/slot/port — ZTE: chassis/slot/port
    frame = models.PositiveIntegerField(default=0, verbose_name='Frame/Chassis')
    slot  = models.PositiveIntegerField(default=0, verbose_name='Slot')
    port  = models.PositiveIntegerField(default=0, verbose_name='PON Port')

    # SNMP polling-এর জন্য OID index (vendor-specific)
    pon_index    = models.CharField(max_length=50, blank=True, verbose_name='SNMP PON Index')
    description  = models.CharField(max_length=100, blank=True)
    max_onus     = models.PositiveIntegerField(default=128)
    current_onus = models.PositiveIntegerField(default=0)
    is_active    = models.BooleanField(default=True)
    synced_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table     = 'olt_ports'
        unique_together = ['olt', 'frame', 'slot', 'port']
        verbose_name = 'OLT Port'
        ordering     = ['olt', 'frame', 'slot', 'port']

    def __str__(self):
        return f"{self.olt.name} {self.frame}/{self.slot}/{self.port}"

    @property
    def port_label(self):
        return f"{self.frame}/{self.slot}/{self.port}"


class ONU(models.Model):
    """
    ONU (Optical Network Unit) / ONT device-এর তথ্য।
    প্রতিটি ONU-র RX power, status এবং client mapping এখানে।
    """

    class ONUStatus(models.TextChoices):
        ONLINE         = 'online',         'Online'
        OFFLINE        = 'offline',        'Offline'
        UNAUTHORIZED   = 'unauthorized',   'Unauthorized'
        AUTHORIZED     = 'authorized',     'Authorized'
        PENDING_AUTH   = 'pending_auth',   'Pending Authorization'
        PENDING_DELETE = 'pending_delete', 'Pending Delete'
        LOS            = 'los',            'LOS (Loss of Signal)'
        DYING_GASP     = 'dying_gasp',     'Dying Gasp'

    class PendingAction(models.TextChoices):
        NONE      = 'none',      'No Action'
        AUTHORIZE = 'authorize', 'Authorize'
        DELETE    = 'delete',    'Delete'
        REBOOT    = 'reboot',    'Reboot'

    olt        = models.ForeignKey(OLT, on_delete=models.CASCADE, related_name='onus')
    port       = models.ForeignKey(OLTPort, on_delete=models.CASCADE, related_name='onus', null=True, blank=True)

    # ONU identification
    onu_id        = models.PositiveIntegerField(verbose_name='ONU ID on PON Port')
    serial_number = models.CharField(max_length=64, blank=True, db_index=True, verbose_name='Serial Number')
    mac_address   = models.CharField(max_length=20, blank=True)
    vendor        = models.CharField(max_length=50, blank=True, verbose_name='ONU Vendor')
    model         = models.CharField(max_length=100, blank=True, verbose_name='ONU Model')
    description   = models.CharField(max_length=200, blank=True)

    # Optical Signal (সর্বশেষ পাওয়া reading)
    rx_power       = models.FloatField(null=True, blank=True, verbose_name='RX Power (dBm)')
    tx_power       = models.FloatField(null=True, blank=True, verbose_name='TX Power (dBm)')
    olt_rx_power   = models.FloatField(null=True, blank=True, verbose_name='OLT-side RX Power (dBm)')
    temperature    = models.FloatField(null=True, blank=True, verbose_name='ONU Temperature (°C)')
    voltage        = models.FloatField(null=True, blank=True, verbose_name='ONU Voltage (V)')
    bias_current   = models.FloatField(null=True, blank=True, verbose_name='Bias Current (mA)')
    distance       = models.FloatField(null=True, blank=True, verbose_name='Distance from OLT (km)')

    # RX Power threshold (alert-এর জন্য)
    rx_power_threshold_warn  = models.FloatField(default=-25.0, verbose_name='Warn Threshold (dBm)')
    rx_power_threshold_crit  = models.FloatField(default=-27.0, verbose_name='Critical Threshold (dBm)')

    # Status ও pending action
    status         = models.CharField(max_length=20, choices=ONUStatus.choices, default=ONUStatus.UNAUTHORIZED)
    pending_action = models.CharField(max_length=20, choices=PendingAction.choices, default=PendingAction.NONE)

    # Network তথ্য
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    pppoe_username = models.CharField(max_length=64, blank=True)

    # Client mapping (কোন client এই ONU ব্যবহার করছে)
    client = models.OneToOneField(
        'clients.Client',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='onu'
    )

    # Timestamps
    last_seen      = models.DateTimeField(null=True, blank=True)
    authorized_at  = models.DateTimeField(null=True, blank=True)
    last_polled    = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'olt_onus'
        unique_together = ['olt', 'port', 'onu_id']
        verbose_name = 'ONU Device'
        ordering     = ['olt', 'port', 'onu_id']

    def __str__(self):
        return f"ONU-{self.onu_id} @ {self.port} SN:{self.serial_number}"

    @property
    def rx_power_status(self):
        """RX power-এর ভিত্তিতে signal quality বলে দেওয়া।"""
        if self.rx_power is None:
            return 'unknown'
        if self.rx_power >= -20:
            return 'excellent'
        if self.rx_power >= -24:
            return 'good'
        if self.rx_power >= self.rx_power_threshold_warn:
            return 'fair'
        if self.rx_power >= self.rx_power_threshold_crit:
            return 'warning'
        return 'critical'

    @property
    def is_signal_critical(self):
        return self.rx_power is not None and self.rx_power < self.rx_power_threshold_crit


class ONUSignalLog(models.Model):
    """
    ONU-র optical signal (RX dBm) time-series data।
    Celery task প্রতি ৫ মিনিটে SNMP poll করে এখানে save করে।
    Frontend-এ graph chart দেখানোর জন্য।
    """
    onu          = models.ForeignKey(ONU, on_delete=models.CASCADE, related_name='signal_logs')
    rx_power     = models.FloatField(null=True, blank=True, verbose_name='RX Power (dBm)')
    tx_power     = models.FloatField(null=True, blank=True, verbose_name='TX Power (dBm)')
    olt_rx_power = models.FloatField(null=True, blank=True, verbose_name='OLT RX (dBm)')
    temperature  = models.FloatField(null=True, blank=True)
    voltage      = models.FloatField(null=True, blank=True)
    status       = models.CharField(max_length=20, blank=True)
    recorded_at  = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table  = 'olt_onu_signal_logs'
        verbose_name = 'ONU Signal Log'
        ordering  = ['-recorded_at']
        indexes   = [models.Index(fields=['onu', 'recorded_at'])]

    def __str__(self):
        return f"{self.onu} | {self.rx_power} dBm @ {self.recorded_at:%Y-%m-%d %H:%M}"


class ONUEvent(models.Model):
    """
    ONU-র গুরুত্বপূর্ণ events log।
    Online/Offline, Power degradation, Authorize, Delete events।
    """

    class EventType(models.TextChoices):
        ONLINE             = 'online',             'ONU Online'
        OFFLINE            = 'offline',            'ONU Offline'
        LOS                = 'los',                'Loss of Signal'
        DYING_GASP         = 'dying_gasp',         'Dying Gasp'
        AUTHORIZED         = 'authorized',         'ONU Authorized'
        DELETED            = 'deleted',            'ONU Deleted'
        REBOOTED           = 'rebooted',           'ONU Rebooted'
        POWER_DEGRADED     = 'power_degraded',     'Signal Power Degraded'
        POWER_RESTORED     = 'power_restored',     'Signal Power Restored'
        CONFIG_CHANGE      = 'config_change',      'Configuration Changed'

    onu        = models.ForeignKey(ONU, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    details    = models.TextField(blank=True)
    rx_power   = models.FloatField(null=True, blank=True)
    triggered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table  = 'olt_onu_events'
        verbose_name = 'ONU Event'
        ordering  = ['-created_at']


class OLTSNMPOIDProfile(models.Model):
    """
    Vendor-specific SNMP OID configuration।
    প্রতিটি OLT vendor-এর জন্য আলাদা OID set থাকে।
    """
    vendor      = models.CharField(max_length=20, choices=OLT.Vendor.choices, unique=True)
    description = models.TextField(blank=True)

    # ONU list OID
    oid_onu_list       = models.CharField(max_length=200, blank=True)
    # ONU operational status OID
    oid_onu_status     = models.CharField(max_length=200, blank=True)
    # ONU RX power OID (OLT থেকে দেখা)
    oid_onu_rx_power   = models.CharField(max_length=200, blank=True)
    # ONU TX power OID
    oid_onu_tx_power   = models.CharField(max_length=200, blank=True)
    # OLT-side RX power OID
    oid_olt_rx_power   = models.CharField(max_length=200, blank=True)
    # ONU serial number OID
    oid_onu_serial     = models.CharField(max_length=200, blank=True)
    # ONU distance OID
    oid_onu_distance   = models.CharField(max_length=200, blank=True)
    # ONU temperature OID
    oid_onu_temperature = models.CharField(max_length=200, blank=True)
    # ONU voltage OID
    oid_onu_voltage    = models.CharField(max_length=200, blank=True)
    # Power unit scale factor (e.g. 100 means divide by 100 to get dBm)
    power_scale_factor = models.FloatField(default=100.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table  = 'olt_snmp_oid_profiles'
        verbose_name = 'SNMP OID Profile'

    def __str__(self):
        return f"SNMP OID Profile: {self.get_vendor_display()}"
