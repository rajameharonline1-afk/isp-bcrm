# ফাইল: backend/apps/mac_reseller/models.py
# এই ফাইলটি MAC Reseller ব্যবস্থাপনার সমস্ত database model ধারণ করে।

from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from apps.accounts.models import User


class MACReseller(models.Model):
    """
    MAC Reseller-এর মূল তথ্য।
    প্রতিটি reseller-এর নিজস্ব balance account এবং status থাকে।
    """

    class ResellerStatus(models.TextChoices):
        ACTIVE   = 'active',   'Active'
        INACTIVE = 'inactive', 'Inactive'
        BLOCKED  = 'blocked',  'Blocked'

    name          = models.CharField(max_length=255, unique=True, verbose_name='Reseller Name')
    contact       = models.CharField(max_length=20, blank=True, verbose_name='Phone/Contact')
    email         = models.EmailField(blank=True, verbose_name='Email Address')
    address       = models.TextField(blank=True, verbose_name='Address')
    # Reseller-এর বর্তমান account balance
    balance       = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name='Account Balance (৳)'
    )
    status        = models.CharField(
        max_length=10, choices=ResellerStatus.choices,
        default=ResellerStatus.ACTIVE, db_index=True
    )
    # যে Admin এই reseller তৈরি করেছে
    created_by    = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_mac_resellers'
    )
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'mac_resellers'
        verbose_name = 'MAC Reseller'
        ordering     = ['name']

    def __str__(self):
        return f"{self.name} (Balance: {self.balance}৳)"

    @property
    def is_active(self):
        return self.status == self.ResellerStatus.ACTIVE


class MACResellerPackage(models.Model):
    """
    MAC Reseller-দের জন্য ইন্টারনেট প্যাকেজ।
    প্রতিটি প্যাকেজের bandwidth এবং মেয়াদ নির্ধারণ করা হয়।
    """

    name              = models.CharField(max_length=150, unique=True, verbose_name='Package Name')
    description       = models.TextField(blank=True, verbose_name='Description')
    # ডাউনলোড গতি (Mbps)
    bandwidth_down    = models.PositiveIntegerField(verbose_name='Download Speed (Mbps)')
    # আপলোড গতি (Mbps)
    bandwidth_up      = models.PositiveIntegerField(verbose_name='Upload Speed (Mbps)')
    duration_days     = models.PositiveIntegerField(default=30, verbose_name='Duration (Days)')
    # Admin নির্ধারিত retail মূল্য
    retail_price      = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name='Retail Price (৳)'
    )
    is_active         = models.BooleanField(default=True)
    created_by        = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_mac_packages'
    )
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'mac_reseller_packages'
        verbose_name = 'MAC Reseller Package'
        ordering     = ['name']

    def __str__(self):
        return f"{self.name} ({self.bandwidth_down}M/{self.bandwidth_up}M)"


class MACResellerTariffConfig(models.Model):
    """
    MAC Reseller-এর জন্য প্যাকেজ ভিত্তিক মূল্য কনফিগারেশন।
    প্রতিটি reseller-প্যাকেজ জুটির জন্য আলাদা দাম নির্ধারণ করা যায়।
    """

    # কোন reseller-এর জন্য এই tariff
    reseller      = models.ForeignKey(
        MACReseller, on_delete=models.CASCADE,
        related_name='tariff_configs', verbose_name='Reseller'
    )
    # কোন প্যাকেজের tariff
    package       = models.ForeignKey(
        MACResellerPackage, on_delete=models.CASCADE,
        related_name='tariff_configs', verbose_name='Package'
    )
    # Reseller যে মূল্যে কিনবে (Admin থেকে)
    reseller_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name='Reseller Buy Price (৳)'
    )
    # Reseller client-কে যে মূল্যে বিক্রি করতে পারবে
    max_retail_price = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name='Max Allowed Retail Price (৳)'
    )
    is_active     = models.BooleanField(default=True)
    effective_from = models.DateField(verbose_name='Effective From')
    created_by    = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_tariff_configs'
    )
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'mac_reseller_tariff_configs'
        verbose_name    = 'Tariff Config'
        unique_together = [('reseller', 'package')]
        ordering        = ['reseller', 'package']

    def __str__(self):
        return f"{self.reseller.name} → {self.package.name}: {self.reseller_price}৳"

    @property
    def profit_margin(self):
        """Reseller-এর সর্বোচ্চ মুনাফা।"""
        return self.max_retail_price - self.reseller_price


class MACResellerFunding(models.Model):
    """
    MAC Reseller-এর account-এ টাকা যোগ করার রেকর্ড।
    Admin reseller-এর balance top-up করলে এখানে entry হয়।
    """

    class FundingStatus(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        APPROVED  = 'approved',  'Approved'
        REJECTED  = 'rejected',  'Rejected'

    class PaymentMethod(models.TextChoices):
        CASH     = 'cash',     'Cash'
        BKASH    = 'bkash',    'bKash'
        NAGAD    = 'nagad',    'Nagad'
        ROCKET   = 'rocket',   'Rocket'
        BANK     = 'bank',     'Bank Transfer'
        CHEQUE   = 'cheque',   'Cheque'
        ONLINE   = 'online',   'Online'

    reseller       = models.ForeignKey(
        MACReseller, on_delete=models.CASCADE,
        related_name='fundings', verbose_name='Reseller'
    )
    amount         = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("1"))],
        verbose_name='Funding Amount (৳)'
    )
    payment_method = models.CharField(
        max_length=10, choices=PaymentMethod.choices,
        default=PaymentMethod.CASH
    )
    transaction_id = models.CharField(max_length=100, blank=True, verbose_name='Transaction ID / Ref')
    note           = models.TextField(blank=True, verbose_name='Note')
    status         = models.CharField(
        max_length=10, choices=FundingStatus.choices,
        default=FundingStatus.PENDING, db_index=True
    )
    # Balance আগে কত ছিল এবং পরে কত হয়েছে
    balance_before = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_after  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # কে এই funding approve/reject করেছে
    approved_by    = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_fundings'
    )
    approved_at    = models.DateTimeField(null=True, blank=True)
    funded_by      = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_fundings'
    )
    funded_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table  = 'mac_reseller_fundings'
        verbose_name = 'Reseller Funding'
        ordering  = ['-funded_at']
        indexes   = [
            models.Index(fields=['reseller', 'status']),
            models.Index(fields=['status', 'funded_at']),
        ]

    def __str__(self):
        return f"{self.reseller.name} | +{self.amount}৳ | {self.status}"


class ClientPGWPayment(models.Model):
    """
    Client-দের Payment Gateway (PGW)-এর মাধ্যমে করা payment record।
    Reseller-এর অধীনে থাকা client যখন online-এ বিল দেয়, এখানে সংরক্ষিত হয়।
    """

    class PGWStatus(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        SUCCESS   = 'success',   'Success'
        FAILED    = 'failed',    'Failed'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED  = 'refunded',  'Refunded'

    class PaymentGateway(models.TextChoices):
        BKASH      = 'bkash',      'bKash'
        NAGAD      = 'nagad',      'Nagad'
        ROCKET     = 'rocket',     'Rocket'
        SSLCOMMERZ = 'sslcommerz', 'SSL Commerz'
        UPAY       = 'upay',       'Upay'
        DMONEY     = 'dmoney',     'Dmoney'
        OTHER      = 'other',      'Other'

    client          = models.ForeignKey(
        'clients.Client', on_delete=models.CASCADE,
        related_name='pgw_payments', verbose_name='Client'
    )
    # কোন reseller-এর মাধ্যমে payment হয়েছে
    reseller        = models.ForeignKey(
        MACReseller, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='client_pgw_payments', verbose_name='Reseller'
    )
    # কোন billing-এর জন্য payment
    billing         = models.ForeignKey(
        'billing.Billing', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pgw_payments', verbose_name='Related Billing'
    )
    amount          = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal("1"))],
        verbose_name='Payment Amount (৳)'
    )
    gateway         = models.CharField(
        max_length=15, choices=PaymentGateway.choices,
        default=PaymentGateway.BKASH, verbose_name='Payment Gateway'
    )
    # Gateway-এর transaction reference number
    pgw_transaction_id = models.CharField(max_length=200, blank=True, verbose_name='PGW Transaction ID')
    # আমাদের সিস্টেমের internal order/reference
    order_id        = models.CharField(max_length=100, unique=True, verbose_name='Order ID')
    status          = models.CharField(
        max_length=10, choices=PGWStatus.choices,
        default=PGWStatus.PENDING, db_index=True
    )
    # Gateway থেকে পাওয়া raw response data
    gateway_response = models.JSONField(default=dict, blank=True)
    # Processing fee যদি থাকে
    processing_fee  = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    note            = models.TextField(blank=True)
    payment_date    = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table  = 'client_pgw_payments'
        verbose_name = 'Client PGW Payment'
        ordering  = ['-created_at']
        indexes   = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['client', 'status']),
            models.Index(fields=['reseller', 'status']),
        ]

    def __str__(self):
        return f"{self.client.username} | {self.gateway} | {self.amount}৳ | {self.status}"

    @property
    def net_amount(self):
        """Processing fee বাদ দিয়ে net amount।"""
        return self.amount - self.processing_fee


class PGWTransactionSettlement(models.Model):
    """
    PGW payment-এর settlement record।
    Reseller-দের সাথে PGW payment settlement করার হিসাব।
    """

    class SettlementStatus(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        COMPLETED = 'completed', 'Completed'
        PARTIAL   = 'partial',   'Partial'

    reseller          = models.ForeignKey(
        MACReseller, on_delete=models.CASCADE,
        related_name='settlements', verbose_name='Reseller'
    )
    # এই settlement period-এ কতগুলো payment include হয়েছে
    payment_count     = models.PositiveIntegerField(default=0, verbose_name='No. of Payments')
    # Total gross amount
    total_amount      = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name='Total Payment Amount (৳)'
    )
    # Total processing fee
    total_fee         = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Total Processing Fee (৳)'
    )
    # Net settlement amount (total - fee)
    net_settlement    = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        verbose_name='Net Settlement Amount (৳)'
    )
    # যে payments এই settlement-এ include হয়েছে
    payments          = models.ManyToManyField(
        ClientPGWPayment, related_name='settlements', blank=True
    )
    settlement_date   = models.DateField(verbose_name='Settlement Date')
    status            = models.CharField(
        max_length=10, choices=SettlementStatus.choices,
        default=SettlementStatus.PENDING, db_index=True
    )
    note              = models.TextField(blank=True)
    settled_by        = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pgw_settlements'
    )
    settled_at        = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table  = 'pgw_transaction_settlements'
        verbose_name = 'PGW Transaction Settlement'
        ordering  = ['-settlement_date']
        indexes   = [
            models.Index(fields=['reseller', 'status']),
            models.Index(fields=['status', 'settlement_date']),
        ]

    def __str__(self):
        return f"{self.reseller.name} | {self.settlement_date} | {self.net_settlement}৳ | {self.status}"


class MACResellerNotice(models.Model):
    """
    MAC Reseller-দের জন্য নোটিস।
    Admin নির্দিষ্ট বা সব reseller-কে নোটিস পাঠাতে পারবে।
    """

    class NoticeType(models.TextChoices):
        GENERAL   = 'general',   'General Notice'
        BILLING   = 'billing',   'Billing Notice'
        SYSTEM    = 'system',    'System Update'
        URGENT    = 'urgent',    'Urgent'
        PROMOTION = 'promotion', 'Promotion'

    title            = models.CharField(max_length=255, verbose_name='Notice Title')
    content          = models.TextField(verbose_name='Notice Content')
    notice_type      = models.CharField(
        max_length=15, choices=NoticeType.choices,
        default=NoticeType.GENERAL
    )
    # খালি হলে সব active reseller পাবে
    target_resellers = models.ManyToManyField(
        MACReseller, blank=True,
        related_name='notices',
        verbose_name='Target Resellers (empty = all)'
    )
    is_active        = models.BooleanField(default=True)
    # কখন থেকে notice দেখাবে
    publish_at       = models.DateTimeField(verbose_name='Publish At')
    # কখন পর্যন্ত notice দেখাবে (null = indefinite)
    expire_at        = models.DateTimeField(null=True, blank=True, verbose_name='Expire At')
    created_by       = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_notices'
    )
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table  = 'mac_reseller_notices'
        verbose_name = 'MAC Reseller Notice'
        ordering  = ['-publish_at']

    def __str__(self):
        return f"[{self.notice_type.upper()}] {self.title}"
