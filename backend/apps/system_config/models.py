# ফাইল: backend/apps/system_config/models.py
# এই ফাইলটি Company, Invoice, Email, Payment Gateway ও System settings-এর database model ধারণ করে।

from django.db import models
from apps.accounts.models import User
# সংবেদনশীল তথ্য (password/API key) encrypted রাখার জন্য servers app-এর field ব্যবহার করা হয়েছে
from apps.servers.models import EncryptedField


class SingletonModel(models.Model):
    """
    এই abstract model-এ সবসময় মাত্র একটি row থাকবে (pk=1)।
    Company/Email/System setting-এর মতো একক কনফিগারেশনের জন্য ব্যবহৃত।
    """
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+')

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # সবসময় একই row আপডেট হবে, নতুন row তৈরি হবে না
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Singleton row মুছে ফেলা যাবে না
        pass

    @classmethod
    def load(cls):
        """Setting row আনে; না থাকলে default মান দিয়ে তৈরি করে।"""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class CompanySetting(SingletonModel):
    """কোম্পানির নাম, ঠিকানা, লোগো ইত্যাদি — invoice ও SMS-এ ব্যবহৃত হয়।"""
    name        = models.CharField(max_length=150, default='ISP Company')
    email       = models.EmailField(blank=True)
    phone       = models.CharField(max_length=30, blank=True)
    address     = models.TextField(blank=True)
    website     = models.URLField(blank=True)
    logo        = models.ImageField(upload_to='company/', blank=True, null=True)
    currency    = models.CharField(max_length=10, default='BDT')
    # BTRC license ইত্যাদি রিপোর্টে লাগে
    license_no  = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table     = 'system_company_settings'
        verbose_name = 'Company Setting'

    def __str__(self):
        return self.name


class InvoiceSetting(SingletonModel):
    """Invoice-এর prefix, নম্বর, footer ও terms নিয়ন্ত্রণ করে।"""
    class PaperSize(models.TextChoices):
        A4   = 'a4',   'A4'
        A5   = 'a5',   'A5'
        POS  = 'pos',  'POS (80mm)'

    prefix        = models.CharField(max_length=10, default='INV')
    next_number   = models.PositiveIntegerField(default=1)
    paper_size    = models.CharField(max_length=5, choices=PaperSize.choices, default=PaperSize.A4)
    show_logo     = models.BooleanField(default=True)
    footer_note   = models.CharField(max_length=255, blank=True)
    terms         = models.TextField(blank=True)

    class Meta:
        db_table     = 'system_invoice_settings'
        verbose_name = 'Invoice Setting'

    def __str__(self):
        return f"Invoice Setting ({self.prefix})"


class EmailSetting(SingletonModel):
    """SMTP email সার্ভারের তথ্য। Password encrypted অবস্থায় থাকে।"""
    host        = models.CharField(max_length=150, blank=True)
    port        = models.PositiveIntegerField(default=587)
    use_tls     = models.BooleanField(default=True)
    use_ssl     = models.BooleanField(default=False)
    username    = models.CharField(max_length=150, blank=True)
    password    = EncryptedField(blank=True, default='')
    from_email  = models.EmailField(blank=True)
    from_name   = models.CharField(max_length=100, blank=True)
    is_active   = models.BooleanField(default=False)

    class Meta:
        db_table     = 'system_email_settings'
        verbose_name = 'Email Setting'

    def __str__(self):
        return f"Email Setting ({self.host or 'not configured'})"


class PaymentGateway(models.Model):
    """
    Payment gateway-এর credentials (bKash, Nagad, SSL Commerz ইত্যাদি)।
    Secret field গুলো encrypted থাকে এবং API response-এ কখনো ফেরত যায় না।
    """
    class Provider(models.TextChoices):
        SSLCOMMERZ = 'sslcommerz', 'SSL Commerz'
        BKASH      = 'bkash',      'bKash'
        NAGAD      = 'nagad',      'Nagad'
        ROCKET     = 'rocket',     'Rocket'
        OTHER      = 'other',      'Other'

    provider        = models.CharField(max_length=15, choices=Provider.choices, unique=True)
    display_name    = models.CharField(max_length=100, blank=True)
    store_id        = models.CharField(max_length=150, blank=True)
    store_password  = EncryptedField(blank=True, default='')
    api_key         = EncryptedField(blank=True, default='')
    api_secret      = EncryptedField(blank=True, default='')
    is_sandbox      = models.BooleanField(default=True)
    is_active       = models.BooleanField(default=False)
    # Provider-ভেদে অতিরিক্ত কনফিগারেশন (callback URL ইত্যাদি) — secret রাখা যাবে না
    extra_config    = models.JSONField(default=dict, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'system_payment_gateways'
        verbose_name = 'Payment Gateway'
        ordering     = ['provider']

    def __str__(self):
        return self.display_name or self.get_provider_display()


class PaymentProcessingFee(models.Model):
    """Gateway দিয়ে payment করলে কত fee কাটা হবে এবং কে বহন করবে তা নির্ধারণ করে।"""
    class FeeType(models.TextChoices):
        PERCENT = 'percent', 'Percentage'
        FIXED   = 'fixed',   'Fixed Amount'

    class BornBy(models.TextChoices):
        CLIENT  = 'client',  'Client pays'
        COMPANY = 'company', 'Company pays'

    gateway     = models.ForeignKey(PaymentGateway, on_delete=models.CASCADE,
                                    related_name='fees')
    fee_type    = models.CharField(max_length=8, choices=FeeType.choices, default=FeeType.PERCENT)
    value       = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    born_by     = models.CharField(max_length=8, choices=BornBy.choices, default=BornBy.CLIENT)
    min_fee     = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    max_fee     = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    is_active   = models.BooleanField(default=True)

    class Meta:
        db_table     = 'system_payment_processing_fees'
        verbose_name = 'Payment Processing Fee'

    def __str__(self):
        return f"{self.gateway} - {self.value} ({self.fee_type})"

    def calculate(self, amount):
        """নির্দিষ্ট amount-এর জন্য processing fee হিসাব করে।"""
        from decimal import Decimal, ROUND_HALF_UP
        amount = Decimal(str(amount))
        fee = amount * self.value / 100 if self.fee_type == self.FeeType.PERCENT else self.value
        fee = max(fee, self.min_fee)
        if self.max_fee is not None:
            fee = min(fee, self.max_fee)
        return fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class SystemSetting(SingletonModel):
    """সিস্টেমের সাধারণ আচরণ — grace period, reminder দিন, SMS চালু/বন্ধ ইত্যাদি।"""
    # মেয়াদ শেষের পর কত দিন অতিরিক্ত সময় দেওয়া হবে
    grace_days              = models.PositiveSmallIntegerField(default=0)
    auto_disable_expired    = models.BooleanField(default=True)
    auto_generate_bills     = models.BooleanField(default=True)
    sms_enabled             = models.BooleanField(default=True)
    email_enabled           = models.BooleanField(default=False)
    expiry_reminder_days    = models.PositiveSmallIntegerField(default=3)
    send_payment_sms        = models.BooleanField(default=True)
    date_format             = models.CharField(max_length=20, default='DD/MM/YYYY')
    timezone                = models.CharField(max_length=50, default='Asia/Dhaka')
    maintenance_mode        = models.BooleanField(default=False)

    class Meta:
        db_table     = 'system_settings'
        verbose_name = 'System Setting'

    def __str__(self):
        return 'System Setting'
