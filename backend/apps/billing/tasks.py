# ফাইল: backend/apps/billing/tasks.py
# Billing-এর automatic Celery background tasks।

import logging
from datetime import date
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def auto_generate_monthly_bills_task(self):
    """
    প্রতিদিন সকালে আজকের bill_date যে সব client-এর তাদের বিল generate করা।
    CELERY_BEAT_SCHEDULE-এ প্রতিদিন সকাল ৬টায় চালানো হবে।
    """
    from apps.billing.services import BillingService
    result = BillingService.auto_generate_monthly_bills()
    logger.info(f"Auto bill task done: {result}")
    return result


@shared_task(bind=True, max_retries=3)
def mark_overdue_bills_task(self):
    """
    Due date অতিক্রান্ত হয়ে গেছে এমন bills Overdue mark করা।
    প্রতিদিন একবার চালানো হয়।
    """
    from apps.billing.models import Billing

    today   = date.today()
    updated = Billing.objects.filter(
        due_date__lt=today,
        status__in=[Billing.BillStatus.UNPAID, Billing.BillStatus.PARTIAL],
    ).update(status=Billing.BillStatus.OVERDUE)

    logger.info(f"Marked {updated} bills as overdue")
    return {'overdue_marked': updated, 'date': str(today)}


@shared_task(bind=True)
def send_due_reminder_sms_task(self):
    """
    Due আছে এমন active client-দের SMS reminder পাঠানো।
    প্রতি সপ্তাহে একবার।
    """
    from apps.clients.models import Client

    from apps.sms.services import SMSService

    clients = Client.objects.filter(
        status=Client.Status.ACTIVE,
        due_amount__gt=0,
    )

    count = 0
    for client in clients:
        try:
            # due_reminder template দিয়ে SMS queue করা (SMS module)
            if SMSService.queue_event('due_reminder', client):
                count += 1
        except Exception as exc:
            logger.error(f"SMS error for {client.phone}: {exc}")

    return {'sms_sent': count}


@shared_task(bind=True)
def generate_bill_for_client_task(self, client_id: int, bill_month_str: str):
    """
    Single client-এর জন্য manual bill generation (API trigger থেকে)।
    bill_month_str = 'YYYY-MM-DD' format।
    """
    from datetime import date as date_cls
    from apps.clients.models import Client
    from apps.billing.services import BillingService

    try:
        client     = Client.objects.get(pk=client_id)
        bill_month = date_cls.fromisoformat(bill_month_str)
        billing, created = BillingService.generate_bill_for_client(client, bill_month)
        return {'billing_id': billing.id, 'created': created}
    except Client.DoesNotExist:
        return {'error': f'Client {client_id} not found'}
    except Exception as exc:
        logger.error(f"Manual bill task error: {exc}")
        raise self.retry(exc=exc, countdown=30)
