# ফাইল: backend/apps/system_config/tasks.py
# এই ফাইলটি Email পাঠানোর সব Celery background tasks ধারণ করে।

import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def send_email_task(self, subject: str, body: str, to, html_body: str = ''):
    """
    একটি email পাঠায়।
    to — একটি address (str) বা address-এর list।
    ব্যর্থ হলে ২ মিনিট পর পুনরায় চেষ্টা করে; সর্বোচ্চ ৩ বার।
    """
    from apps.system_config.services import SystemConfigService

    try:
        sent = SystemConfigService.send_email(subject=subject, body=body, to=to)
        logger.info("Email sent: to=%s subject=%s", to, subject)
        return {'sent': sent, 'to': to}
    except ValueError as exc:
        # Email setup নেই — retry করার দরকার নেই
        logger.warning("Email not configured: %s", exc)
        return {'skipped': True, 'reason': str(exc)}
    except Exception as exc:
        logger.error("Email failed (attempt %d): %s", self.request.retries + 1, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True)
def send_billing_due_email_task(self):
    """
    Due বিল আছে এমন client-দের ইমেইল reminder পাঠানো।
    সাপ্তাহিক একবার — সোমবার সকাল ৯টায় Celery Beat চালাবে।
    """
    from apps.clients.models import Client
    from apps.system_config.services import SystemConfigService
    from apps.system_config.models import CompanySetting

    cfg = SystemConfigService.system()
    if not cfg.email_enabled:
        logger.info("Email disabled in system settings — skipping due reminder")
        return {'skipped': True}

    company = CompanySetting.load()
    clients = Client.objects.filter(
        status=Client.Status.ACTIVE,
        due_amount__gt=0,
        email__isnull=False,
    ).exclude(email='')

    sent = failed = 0
    for client in clients:
        subject = f"[{company.name}] Bill Due Reminder"
        body = (
            f"Dear {client.full_name},\n\n"
            f"Your current due amount is BDT {client.due_amount}.\n"
            f"Please pay before your expiry date: {client.expiry_date}.\n\n"
            f"Thank you,\n{company.name}"
        )
        try:
            # email_task queue করা হচ্ছে — directly পাঠানো হচ্ছে না
            send_email_task.delay(subject=subject, body=body, to=client.email)
            sent += 1
        except Exception as exc:
            logger.error("Queue email failed for %s: %s", client.email, exc)
            failed += 1

    logger.info("Billing due email queued: sent=%d failed=%d", sent, failed)
    return {'queued': sent, 'failed': failed}


@shared_task(bind=True)
def send_expiry_email_task(self, days_before: int = 3):
    """
    Expiry-র নির্দিষ্ট দিন আগে client-দের email পাঠানো।
    SMS reminder-এর পাশাপাশি email-ও যাবে যদি email enabled থাকে।
    """
    from datetime import date, timedelta
    from apps.clients.models import Client
    from apps.system_config.services import SystemConfigService
    from apps.system_config.models import CompanySetting

    cfg = SystemConfigService.system()
    if not cfg.email_enabled:
        return {'skipped': True}

    company       = CompanySetting.load()
    reminder_date = date.today() + timedelta(days=days_before)
    clients = Client.objects.filter(
        status=Client.Status.ACTIVE,
        expiry_date=reminder_date,
        email__isnull=False,
    ).exclude(email='')

    queued = 0
    for client in clients:
        subject = f"[{company.name}] Connection Expiry Reminder"
        body = (
            f"Dear {client.full_name},\n\n"
            f"Your internet connection will expire on {client.expiry_date} "
            f"({days_before} days remaining).\n"
            f"Please renew to continue uninterrupted service.\n\n"
            f"Thank you,\n{company.name}"
        )
        send_email_task.delay(subject=subject, body=body, to=client.email)
        queued += 1

    logger.info("Expiry email queued: %d clients (days_before=%d)", queued, days_before)
    return {'queued': queued, 'days_before': days_before}


@shared_task(bind=True)
def send_payment_confirmation_email_task(self, payment_id: int):
    """
    Payment সফল হলে client-কে confirmation email পাঠানো।
    Payment collect হওয়ার পরে এই task queue করা হবে।
    """
    from apps.billing.models import Payment
    from apps.system_config.services import SystemConfigService
    from apps.system_config.models import CompanySetting

    cfg = SystemConfigService.system()
    if not cfg.email_enabled:
        return {'skipped': True}

    try:
        payment = Payment.objects.select_related('client', 'billing').get(pk=payment_id)
    except Payment.DoesNotExist:
        return {'error': f'Payment {payment_id} not found'}

    client  = payment.client
    if not client.email:
        return {'skipped': True, 'reason': 'No email'}

    company = CompanySetting.load()
    subject = f"[{company.name}] Payment Confirmation - BDT {payment.amount}"
    body = (
        f"Dear {client.full_name},\n\n"
        f"We have received your payment of BDT {payment.amount} "
        f"via {payment.get_method_display()}.\n"
        f"Transaction ID: {payment.transaction_id or 'N/A'}\n"
        f"Date: {payment.payment_date.strftime('%d %b %Y %I:%M %p')}\n\n"
        f"Thank you for your payment.\n{company.name}"
    )
    send_email_task.delay(subject=subject, body=body, to=client.email)
    return {'queued': True, 'payment_id': payment_id, 'to': client.email}
