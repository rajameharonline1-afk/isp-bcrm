# ফাইল: backend/apps/sms/services.py
# এই ফাইলটি SMS তৈরি, template render ও gateway-তে পাঠানোর business logic ধারণ করে।

import re
import logging
import requests
from django.utils import timezone

from apps.system_config.services import SystemConfigService
from .models import SMSGateway, SMSTemplate, SMSMessage

logger = logging.getLogger(__name__)

_VAR = re.compile(r'\{\{\s*(\w+)\s*\}\}')


class SMSService:
    """SMS পাঠানোর সব কাজ এখানে; view ও task শুধু এই class কল করে।"""

    @staticmethod
    def normalize_phone(phone):
        """01XXXXXXXXX / +8801XXXXXXXXX / 8801XXXXXXXXX — সব 8801XXXXXXXXX রূপে আনে।"""
        digits = re.sub(r'\D', '', str(phone))
        if digits.startswith('88'):
            digits = digits[2:]
        if not re.match(r'^01[3-9]\d{8}$', digits):
            raise ValueError(f'Invalid phone number: {phone}')
        return '88' + digits

    @staticmethod
    def count_segments(text):
        """বাংলা (Unicode) SMS-এ ৭০/৬৭ অক্ষরে এক part, ইংরেজিতে ১৬০/১৫৩।"""
        text = text or ''
        if any(ord(c) > 127 for c in text):
            single, multi = 70, 67
        else:
            single, multi = 160, 153
        return 1 if len(text) <= single else -(-len(text) // multi)

    @staticmethod
    def render(body, context):
        """{{variable}} গুলো context-এর মান দিয়ে বদলায়; অজানা variable ফাঁকা হয়ে যায়।"""
        return _VAR.sub(lambda m: str(context.get(m.group(1), '')), body)

    @staticmethod
    def client_context(client, **extra):
        """Client থেকে template variable তৈরি করে।"""
        ctx = {
            'full_name': client.full_name, 'username': client.username,
            'phone': client.phone, 'due_amount': client.due_amount,
            'monthly_bill': client.monthly_bill, 'expiry_date': client.expiry_date or '',
            'company_name': SystemConfigService.company().name,
        }
        ctx.update(extra)
        return ctx

    @staticmethod
    def queue(phone, message, client=None, template=None, sent_by=None):
        """SMS log তৈরি করে Celery task-এ পাঠায়। SMS বন্ধ থাকলে None ফেরত দেয়।"""
        if not SystemConfigService.system().sms_enabled:
            return None
        sms = SMSMessage.objects.create(
            recipient=SMSService.normalize_phone(phone), message=message,
            sms_count=SMSService.count_segments(message),
            client=client, template=template, sent_by=sent_by,
        )
        from .tasks import send_sms_task
        send_sms_task.delay(sms.id)
        return sms

    @staticmethod
    def queue_event(event, client, **extra):
        """Event-এর (যেমন due_reminder) active template দিয়ে client-কে SMS পাঠায়।"""
        template = SMSTemplate.objects.filter(event=event, is_active=True).first()
        if template is None:
            logger.warning('No active SMS template for event %s', event)
            return None
        body = SMSService.render(template.body, SMSService.client_context(client, **extra))
        return SMSService.queue(client.phone, body, client=client, template=template)

    @staticmethod
    def deliver(sms):
        """একটি SMSMessage gateway-তে পাঠায় এবং ফলাফল log-এ লেখে। সফল হলে True।"""
        gateway = (sms.gateway if sms.gateway and sms.gateway.is_active else
                   SMSGateway.objects.filter(is_active=True).order_by('-is_default').first())
        sms.attempts += 1
        if gateway is None:
            sms.status, sms.response = SMSMessage.Status.FAILED, 'No active SMS gateway.'
            sms.save()
            return False

        values = {'api_key': gateway.api_key, 'secret_key': gateway.secret_key,
                  'sender_id': gateway.sender_id, 'to': sms.recipient, 'message': sms.message}
        # Template-এর প্রতিটি মানে placeholder বসানো (str.replace — format() নয়, কারণ বার্তায় { } থাকতে পারে)
        params = {}
        for key, tpl in gateway.params_template.items():
            val = str(tpl)
            for name, real in values.items():
                val = val.replace('{' + name + '}', str(real))
            params[key] = val

        sms.gateway = gateway
        try:
            if gateway.http_method == SMSGateway.Method.GET:
                resp = requests.get(gateway.api_url, params=params, timeout=15)
            else:
                resp = requests.post(gateway.api_url, data=params, timeout=15)
            ok = resp.ok and (not gateway.success_keyword or gateway.success_keyword in resp.text)
            sms.response = resp.text[:500]
        except requests.RequestException as exc:
            ok, sms.response = False, str(exc)[:500]

        sms.status = SMSMessage.Status.SENT if ok else SMSMessage.Status.FAILED
        sms.sent_at = timezone.now() if ok else None
        sms.save()
        return ok
