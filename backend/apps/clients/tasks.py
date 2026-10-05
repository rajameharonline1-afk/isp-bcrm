# ফাইল: backend/apps/clients/tasks.py
# Client-এর automatic background tasks — Celery দিয়ে চালানো হয়।

import logging
from datetime import date
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def disable_expired_clients_task(self):
    """
    প্রতিদিন expired client-দের automatic disable করা।
    Expiry date অতিক্রান্ত হলে Mikrotik ও RADIUS-এ disable।
    """
    from apps.clients.models import Client
    from apps.clients.services import ClientService

    today    = date.today()
    expired  = Client.objects.filter(
        status=Client.Status.ACTIVE,
        expiry_date__lt=today,
    ).select_related('router')

    count = 0
    for client in expired:
        try:
            ClientService.disable_client(client, reason='Auto expired')
            count += 1
        except Exception as exc:
            logger.error(f"Failed to disable expired client {client.username}: {exc}")

    logger.info(f"Auto disabled {count} expired clients")
    return {'disabled_count': count, 'date': str(today)}


@shared_task(bind=True)
def send_expiry_reminder_sms_task(self, days_before=3):
    """
    Expiry-র {days_before} দিন আগে client-দের SMS reminder পাঠানো।
    """
    from apps.clients.models import Client
    from datetime import timedelta

    reminder_date = date.today() + timedelta(days=days_before)
    clients = Client.objects.filter(
        status=Client.Status.ACTIVE,
        expiry_date=reminder_date,
    ).values('id', 'full_name', 'phone', 'username', 'expiry_date')

    count = 0
    for client in clients:
        try:
            # SMS পাঠানো (SMS module integrate হলে এখানে call করতে হবে)
            logger.info(f"SMS reminder: {client['phone']} expires {client['expiry_date']}")
            count += 1
        except Exception as exc:
            logger.error(f"SMS failed for {client['phone']}: {exc}")

    return {'sms_sent': count, 'days_before': days_before}


@shared_task(bind=True)
def reset_renewal_flags_task(self):
    """
    প্রতি মাসের ১ তারিখে সব client-এর is_renewed flag reset করা।
    এতে billing cycle সঠিক থাকে।
    """
    from apps.clients.models import Client

    today = date.today()
    if today.day == 1:
        updated = Client.objects.filter(is_renewed=True).update(is_renewed=False, renewed_at=None)
        logger.info(f"Reset is_renewed for {updated} clients")
        return {'reset_count': updated}

    return {'skipped': True, 'reason': 'Not 1st of month'}


@shared_task(bind=True, max_retries=2)
def sync_client_to_mikrotik_radius_task(self, client_id: int):
    """
    Single client-কে Mikrotik ও RADIUS-এ sync করা।
    Client import বা manual trigger-এর পরে ব্যবহার হয়।
    """
    from apps.clients.models import Client
    from apps.clients.services import ClientService

    try:
        client = Client.objects.select_related('router', 'package').get(pk=client_id)
        _, sync_results = ClientService.create_client.__wrapped__(
            validated_data={}, created_by=None,
        )
        return {'client_id': client_id, 'sync': sync_results}
    except Client.DoesNotExist:
        logger.error(f"Client {client_id} not found for sync")
        return {'error': 'Client not found'}
    except Exception as exc:
        logger.error(f"Sync failed for client {client_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)
