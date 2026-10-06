# ফাইল: backend/apps/sms/management/commands/seed_sms_templates.py
# এই কমান্ড স্বয়ংক্রিয় reminder SMS-এর জন্য ডিফল্ট template তৈরি করে (python manage.py seed_sms_templates)।

from django.core.management.base import BaseCommand
from apps.sms.models import SMSTemplate

DEFAULTS = [
    ('Due Reminder', 'due_reminder',
     'Dear {{full_name}}, your internet bill due is {{due_amount}} BDT. Please pay to keep your connection active. - {{company_name}}'),
    ('Expiry Reminder', 'expiry_reminder',
     'Dear {{full_name}}, your internet connection expires on {{expiry_date}}. Please renew. - {{company_name}}'),
    ('Payment Received', 'payment_received',
     'Dear {{full_name}}, we received your payment. Thank you. - {{company_name}}'),
    ('Welcome', 'welcome',
     'Welcome {{full_name}}! Your username is {{username}}. - {{company_name}}'),
]


class Command(BaseCommand):
    help = 'Create default SMS templates if they do not exist.'

    def handle(self, *args, **options):
        for name, event, body in DEFAULTS:
            _, created = SMSTemplate.objects.get_or_create(
                name=name, defaults={'event': event, 'body': body})
            self.stdout.write(f"{'created' if created else 'exists '}: {name}")
