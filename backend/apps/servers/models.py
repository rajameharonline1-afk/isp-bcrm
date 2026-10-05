# ফাইল: backend/apps/servers/models.py
# এই ফাইলটি Mikrotik Router এবং FreeRADIUS server-এর সব database model ধারণ করে।

from django.db import models
from django.utils import timezone
from cryptography.fernet import Fernet
from django.conf import settings
import base64
import hashlib

from apps.accounts.models import User


def _get_fernet():
    """Settings থেকে encryption key তৈরি করা (SECRET_KEY ব্যবহার করে)।"""
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


class EncryptedField(models.TextField):
    """Password সহ sensitive data encrypted রাখার জন্য custom field।"""

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        try:
            f = _get_fernet()
            return f.decrypt(value.encode()).decode()
        except Exception:
            return value

    def get_prep_value(self, value):
        if value is None:
            return value
        try:
            # আগে থেকে encrypted কিনা check করা
            _get_fernet().decrypt(value.encode())
            return value
        except Exception:
            f = _get_fernet()
            return f.encrypt(value.encode()).decode()


class MikrotikRouter(models.Model):
    """
    Mikrotik Router-এর তথ্য সংরক্ষণের model।
    প্রতিটি router-এর API connection credentials এখানে encrypted আকারে রাখা হয়।
    """

    class RouterStatus(models.TextChoices):
        ONLINE = 'online', 'Online'
        OFFLINE = 'offline', 'Offline'
        UNKNOWN = 'unknown', 'Unknown'

    # Router-এর মূল তথ্য
    name = models.CharField(max_length=100, verbose_name='Router Name')
    ip_address = models.GenericIPAddressField(verbose_name='Router IP Address')
    api_port = models.PositiveIntegerField(default=8728, verbose_name='RouterOS API Port')
    api_username = models.CharField(max_length=100, verbose_name='API Username')
    api_password = EncryptedField(verbose_name='API Password (Encrypted)')

    # SSH access (backup এবং CLI commands-এর জন্য)
    ssh_port = models.PositiveIntegerField(default=22, verbose_name='SSH Port')
    ssh_username = models.CharField(max_length=100, blank=True, verbose_name='SSH Username')
    ssh_password = EncryptedField(blank=True, verbose_name='SSH Password (Encrypted)')

    # FreeRADIUS NAS তথ্য (COA/Disconnect packet পাঠানোর জন্য)
    nas_identifier = models.CharField(max_length=64, blank=True, verbose_name='NAS Identifier')
    nas_secret = EncryptedField(blank=True, verbose_name='NAS Secret (Encrypted)')
    nas_port = models.PositiveIntegerField(default=3799, verbose_name='NAS CoA Port')

    # Description ও Status
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=10,
        choices=RouterStatus.choices,
        default=RouterStatus.UNKNOWN
    )
    last_checked = models.DateTimeField(null=True, blank=True, verbose_name='Last Status Check')
    last_backup = models.DateTimeField(null=True, blank=True, verbose_name='Last Backup Time')

    # Zone সংযোগ (কোন zone-এ এই router আছে)
    zone = models.ForeignKey(
        'configuration.Zone',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='routers'
    )

    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'servers_mikrotik_routers'
        verbose_name = 'Mikrotik Router'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.ip_address})"

    def get_api_credentials(self):
        """API connection-এর জন্য credentials dictionary return করে।"""
        return {
            'host': self.ip_address,
            'port': self.api_port,
            'username': self.api_username,
            'password': self.api_password,
        }


class RouterPPPoEProfile(models.Model):
    """
    Mikrotik Router-এ তৈরি PPPoE Profile-এর তালিকা।
    প্রতিটি package-এর জন্য একটি profile Mikrotik-এ থাকে।
    """
    router = models.ForeignKey(MikrotikRouter, on_delete=models.CASCADE, related_name='pppoe_profiles')
    profile_name = models.CharField(max_length=100, verbose_name='Profile Name (Mikrotik-এ)')
    local_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='Local Address Pool')
    remote_address = models.CharField(max_length=100, blank=True, verbose_name='Remote Address Pool')
    rate_limit = models.CharField(max_length=50, blank=True, verbose_name='Rate Limit (e.g. 10M/10M)')
    dns_server = models.CharField(max_length=100, blank=True, verbose_name='DNS Server')

    # সংশ্লিষ্ট package (configuration.Package)
    package = models.ForeignKey(
        'configuration.Package',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='router_profiles'
    )

    synced_at = models.DateTimeField(null=True, blank=True, verbose_name='Last Synced from Router')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'servers_pppoe_profiles'
        unique_together = ['router', 'profile_name']
        verbose_name = 'PPPoE Profile'

    def __str__(self):
        return f"{self.profile_name} @ {self.router.name}"


class RouterBackup(models.Model):
    """Router backup ফাইলের তালিকা ও ডাউনলোড লিংক।"""

    router = models.ForeignKey(MikrotikRouter, on_delete=models.CASCADE, related_name='backups')
    backup_file = models.FileField(upload_to='router_backups/', null=True, blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(default=0, verbose_name='File Size (bytes)')
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'servers_router_backups'
        verbose_name = 'Router Backup'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.router.name} backup - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class RouterConnectionLog(models.Model):
    """
    Router-এর সাথে API connection-এর log।
    কখন connect হয়েছে, কী command চলেছে, সফল হয়েছে কিনা।
    """

    class ActionType(models.TextChoices):
        CONNECT_TEST = 'connect_test', 'Connection Test'
        PPP_CREATE = 'ppp_create', 'PPPoE Secret Create'
        PPP_ENABLE = 'ppp_enable', 'PPPoE Secret Enable'
        PPP_DISABLE = 'ppp_disable', 'PPPoE Secret Disable'
        PPP_DELETE = 'ppp_delete', 'PPPoE Secret Delete'
        PPP_DISCONNECT = 'ppp_disconnect', 'Disconnect Active User'
        BACKUP = 'backup', 'Router Backup'
        IMPORT = 'import', 'Import Clients'
        TRAFFIC = 'traffic', 'Traffic Check'
        PROFILE_SYNC = 'profile_sync', 'Profile Sync'

    router = models.ForeignKey(MikrotikRouter, on_delete=models.CASCADE, related_name='connection_logs')
    action = models.CharField(max_length=30, choices=ActionType.choices)
    target = models.CharField(max_length=100, blank=True, verbose_name='Target (username/interface)')
    is_success = models.BooleanField(default=True)
    message = models.TextField(blank=True)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'servers_router_logs'
        verbose_name = 'Router Connection Log'
        ordering = ['-created_at']


# =============================================
# FreeRADIUS Models
# =============================================

class RadiusServer(models.Model):
    """
    FreeRADIUS server-এর connection তথ্য।
    একাধিক RADIUS server থাকতে পারে।
    """
    name = models.CharField(max_length=100, verbose_name='RADIUS Server Name')
    host = models.CharField(max_length=100, verbose_name='RADIUS Server Host/IP')
    auth_port = models.PositiveIntegerField(default=1812, verbose_name='Auth Port')
    acct_port = models.PositiveIntegerField(default=1813, verbose_name='Accounting Port')
    coa_port = models.PositiveIntegerField(default=3799, verbose_name='CoA Port')
    secret = EncryptedField(verbose_name='Shared Secret (Encrypted)')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'servers_radius_servers'
        verbose_name = 'RADIUS Server'

    def __str__(self):
        return f"{self.name} ({self.host})"


class RadCheck(models.Model):
    """
    FreeRADIUS radcheck table - user authentication credentials।
    এই table-এ user-এর password ও access control attributes থাকে।
    """
    username = models.CharField(max_length=64, db_index=True, verbose_name='PPPoE Username')
    attribute = models.CharField(max_length=64, verbose_name='Attribute')  # Cleartext-Password, Auth-Type
    op = models.CharField(max_length=2, default=':=', verbose_name='Operator')
    value = models.CharField(max_length=253, verbose_name='Value')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'radcheck'  # FreeRADIUS-এর actual table name
        managed = True
        verbose_name = 'Radius Check'

    def __str__(self):
        return f"{self.username}: {self.attribute} {self.op} {self.value}"


class RadReply(models.Model):
    """
    FreeRADIUS radreply table - authentication সফল হলে reply attributes।
    Framed-IP-Address, Mikrotik-Rate-Limit ইত্যাদি এখানে থাকে।
    """
    username = models.CharField(max_length=64, db_index=True)
    attribute = models.CharField(max_length=64)
    op = models.CharField(max_length=2, default='=')
    value = models.CharField(max_length=253)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'radreply'  # FreeRADIUS-এর actual table name
        managed = True
        verbose_name = 'Radius Reply'


class RadUserGroup(models.Model):
    """
    FreeRADIUS radusergroup table - user কোন group-এ আছে।
    Group মানে package/profile (যেমন: 10Mbps, 20Mbps)।
    """
    username = models.CharField(max_length=64, db_index=True)
    groupname = models.CharField(max_length=64)
    priority = models.IntegerField(default=1)

    class Meta:
        db_table = 'radusergroup'  # FreeRADIUS-এর actual table name
        managed = True
        verbose_name = 'Radius User Group'
        unique_together = ['username', 'groupname']


class RadGroupCheck(models.Model):
    """FreeRADIUS radgroupcheck - group-level check attributes।"""
    groupname = models.CharField(max_length=64, db_index=True)
    attribute = models.CharField(max_length=64)
    op = models.CharField(max_length=2, default=':=')
    value = models.CharField(max_length=253)

    class Meta:
        db_table = 'radgroupcheck'
        managed = True
        verbose_name = 'Radius Group Check'


class RadGroupReply(models.Model):
    """FreeRADIUS radgroupreply - group-level reply attributes (Rate-Limit ইত্যাদি)।"""
    groupname = models.CharField(max_length=64, db_index=True)
    attribute = models.CharField(max_length=64)
    op = models.CharField(max_length=2, default='=')
    value = models.CharField(max_length=253)

    class Meta:
        db_table = 'radgroupreply'
        managed = True
        verbose_name = 'Radius Group Reply'


class RadAcct(models.Model):
    """
    FreeRADIUS radacct table - accounting/session records।
    কতক্ষণ connected ছিল, কত data use করেছে।
    """
    radacctid = models.BigAutoField(primary_key=True)
    acctsessionid = models.CharField(max_length=64)
    acctuniqueid = models.CharField(max_length=32, unique=True)
    username = models.CharField(max_length=64, db_index=True)
    realm = models.CharField(max_length=64, blank=True)
    nasipaddress = models.GenericIPAddressField(db_index=True)
    nasidentifier = models.CharField(max_length=64, blank=True)
    nasportid = models.CharField(max_length=15, blank=True)
    nasporttype = models.CharField(max_length=32, blank=True)
    acctstarttime = models.DateTimeField(null=True, blank=True, db_index=True)
    acctstoptime = models.DateTimeField(null=True, blank=True)
    acctsessiontime = models.BigIntegerField(default=0)
    acctauthentic = models.CharField(max_length=32, blank=True)
    connectinfo_start = models.TextField(blank=True)
    connectinfo_stop = models.TextField(blank=True)
    acctinputoctets = models.BigIntegerField(default=0)    # Download bytes
    acctoutputoctets = models.BigIntegerField(default=0)   # Upload bytes
    calledstationid = models.CharField(max_length=50, blank=True)
    callingstationid = models.CharField(max_length=50, blank=True)
    acctterminatecause = models.CharField(max_length=32, blank=True)
    servicetype = models.CharField(max_length=32, blank=True)
    framedprotocol = models.CharField(max_length=32, blank=True)
    framedipaddress = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'radacct'
        managed = True
        verbose_name = 'Radius Accounting'

    def __str__(self):
        return f"{self.username} - {self.acctstarttime}"
