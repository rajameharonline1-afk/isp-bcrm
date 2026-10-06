# ফাইল: backend/apps/sms/models.py
# এই ফাইলটি SMS Gateway, Template, Group ও পাঠানো SMS-এর log model ধারণ করে।

from django.db import models
from apps.accounts.models import User
from apps.servers.models import EncryptedField


class SMSGateway(models.Model):
    """
    SMS gateway-এর সংযোগ তথ্য। যেকোনো HTTP-ভিত্তিক gateway এখানে সেট করা যায়।
    params_template-এ {api_key}, {secret_key}, {sender_id}, {to}, {message} placeholder ব্যবহার করা হয়।
    """
    class Method(models.TextChoices):
        GET  = 'GET',  'GET'
        POST = 'POST', 'POST'

    name              = models.CharField(max_length=100, unique=True)
    api_url           = models.URLField(max_length=300)
    http_method       = models.CharField(max_length=4, choices=Method.choices, default=Method.POST)
    api_key           = EncryptedField(blank=True, default='')
    secret_key        = EncryptedField(blank=True, default='')
    sender_id         = models.CharField(max_length=30, blank=True)
    # উদাহরণ: {"api_key": "{api_key}", "senderid": "{sender_id}", "number": "{to}", "message": "{message}"}
    params_template   = models.JSONField(default=dict)
    # Response-এ এই লেখা থাকলে SMS সফল ধরা হবে (ফাঁকা হলে HTTP 200 হলেই সফল)
    success_keyword   = models.CharField(max_length=100, blank=True)
    is_default        = models.BooleanField(default=False)
    is_active         = models.BooleanField(default=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'sms_gateways'
        verbose_name = 'SMS Gateway'
        ordering     = ['-is_default', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # একসময় একটিই default gateway থাকবে
        super().save(*args, **kwargs)
        if self.is_default:
            SMSGateway.objects.exclude(pk=self.pk).update(is_default=False)


class SMSTemplate(models.Model):
    """পুনঃব্যবহারযোগ্য SMS বার্তা। {{full_name}}, {{due_amount}} ইত্যাদি variable সমর্থিত।"""
    class Event(models.TextChoices):
        CUSTOM          = 'custom',          'Custom'
        DUE_REMINDER    = 'due_reminder',    'Due Reminder'
        EXPIRY_REMINDER = 'expiry_reminder', 'Expiry Reminder'
        PAYMENT_RECEIVED = 'payment_received', 'Payment Received'
        WELCOME         = 'welcome',         'Welcome'

    name       = models.CharField(max_length=100, unique=True)
    # স্বয়ংক্রিয় SMS-এ event অনুযায়ী template খোঁজা হয়
    event      = models.CharField(max_length=20, choices=Event.choices, default=Event.CUSTOM)
    body       = models.TextField()
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'sms_templates'
        verbose_name = 'SMS Template'
        ordering     = ['name']

    def __str__(self):
        return self.name


class SMSGroup(models.Model):
    """Bulk SMS-এর জন্য প্রাপকের দল — client ও অতিরিক্ত নম্বর মিলিয়ে।"""
    name          = models.CharField(max_length=100, unique=True)
    description   = models.TextField(blank=True)
    clients       = models.ManyToManyField('clients.Client', blank=True, related_name='sms_groups')
    # প্রতি লাইনে বা কমা দিয়ে আলাদা অতিরিক্ত নম্বর
    extra_numbers = models.TextField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'sms_groups'
        verbose_name = 'SMS Group'
        ordering     = ['name']

    def __str__(self):
        return self.name


class SMSMessage(models.Model):
    """প্রতিটি পাঠানো (বা পাঠানোর অপেক্ষায়) SMS-এর log — Messages Report এখান থেকে হবে।"""
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT    = 'sent',    'Sent'
        FAILED  = 'failed',  'Failed'

    recipient   = models.CharField(max_length=20, db_index=True)
    message     = models.TextField()
    sms_count   = models.PositiveSmallIntegerField(default=1)
    status      = models.CharField(max_length=8, choices=Status.choices,
                                   default=Status.PENDING, db_index=True)
    gateway     = models.ForeignKey(SMSGateway, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='messages')
    template    = models.ForeignKey(SMSTemplate, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='messages')
    client      = models.ForeignKey('clients.Client', on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name='sms_messages')
    sent_by     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='sms_sent')
    response    = models.TextField(blank=True)
    attempts    = models.PositiveSmallIntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)
    sent_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table     = 'sms_messages'
        verbose_name = 'SMS Message'
        ordering     = ['-created_at']
        indexes      = [models.Index(fields=['status', 'created_at'])]

    def __str__(self):
        return f"{self.recipient} [{self.status}]"
