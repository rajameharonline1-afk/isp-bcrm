# ফাইল: backend/apps/olt/tasks.py
# এই ফাইলটি OLT SNMP polling, ONU sync ও immediate action-এর Celery tasks ধারণ করে।

import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, soft_time_limit=120)
def poll_olt_snmp(self, olt_id: int):
    """
    একটি OLT-এ SNMP poll করে সব ONU RX power ও status DB-তে save করে।
    Celery Beat প্রতি ৫ মিনিটে সব active OLT-এর জন্য এই task চালায়।
    """
    from apps.olt.services import OLTService

    try:
        result = OLTService.poll_olt_and_save(olt_id)
        return result
    except Exception as e:
        logger.error(f"OLT SNMP poll error (id={olt_id}): {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task
def poll_all_active_olts():
    """
    সব active OLT-এ একসাথে SNMP poll শুরু করে।
    Celery Beat প্রতি ৫ মিনিটে এই task চালায়।
    প্রতিটি OLT আলাদা worker-এ parallel চলে।
    """
    from apps.olt.models import OLT

    olts = OLT.objects.filter(is_active=True).values_list('id', flat=True)
    count = 0
    for olt_id in olts:
        poll_olt_snmp.delay(olt_id)
        count += 1

    logger.info(f"Scheduled SNMP poll for {count} OLTs")
    return {'scheduled': count}


@shared_task(bind=True, max_retries=3)
def authorize_onu_task(self, onu_id: int, user_id: int, **kwargs):
    """
    ONU authorize করার immediate Celery task।
    Django API থেকে এই task queue করা হয়, SSH CLI OLT-এ command পাঠায়।
    Success/failure WebSocket দিয়ে React-এ জানানো হয়।
    """
    from apps.olt.services import OLTService

    try:
        result = OLTService.authorize_onu(onu_id, user_id, **kwargs)
        return result
    except Exception as e:
        logger.error(f"ONU authorize task error (onu_id={onu_id}): {e}")
        raise self.retry(exc=e, countdown=30)


@shared_task(bind=True, max_retries=3)
def delete_onu_task(self, onu_id: int, user_id: int):
    """
    ONU delete করার immediate Celery task।
    SSH CLI দিয়ে OLT-এ delete command পাঠায়।
    """
    from apps.olt.services import OLTService

    try:
        result = OLTService.delete_onu(onu_id, user_id)
        return result
    except Exception as e:
        logger.error(f"ONU delete task error (onu_id={onu_id}): {e}")
        raise self.retry(exc=e, countdown=30)


@shared_task
def cleanup_old_signal_logs(days: int = 90):
    """
    পুরানো ONU signal log entries পরিষ্কার করা।
    ৯০ দিনের বেশি পুরানো signal log মুছে দেওয়া হয়।
    Celery Beat-এ weekly চালানো হয়।
    """
    from apps.olt.models import ONUSignalLog

    cutoff = timezone.now() - timezone.timedelta(days=days)
    deleted, _ = ONUSignalLog.objects.filter(recorded_at__lt=cutoff).delete()
    logger.info(f"Cleaned up {deleted} old ONU signal log entries (>{days} days)")
    return {'deleted': deleted}


@shared_task
def detect_critical_onus():
    """
    Critical RX power level-এর ONU গুলো detect করে alert পাঠানো।
    প্রতি ১৫ মিনিটে চলে। SMS/Email alert পাঠায়।
    """
    from apps.olt.models import ONU, ONUEvent
    from django.db.models import F

    # Critical threshold-এর নিচে থাকা online ONU গুলো
    critical_onus = ONU.objects.filter(
        status='online',
        rx_power__isnull=False,
        rx_power__lt=F('rx_power_threshold_crit'),
    ).select_related('olt', 'client')

    count = 0
    for onu in critical_onus:
        # Event আগে তৈরি হয়নি কিনা check (দুপুরে তৈরি হলে আবার না)
        recent_event = ONUEvent.objects.filter(
            onu=onu,
            event_type=ONUEvent.EventType.POWER_DEGRADED,
            created_at__gte=timezone.now() - timezone.timedelta(hours=1),
        ).exists()

        if not recent_event:
            ONUEvent.objects.create(
                onu=onu,
                event_type=ONUEvent.EventType.POWER_DEGRADED,
                rx_power=onu.rx_power,
                details=f"Critical signal: {onu.rx_power} dBm (threshold: {onu.rx_power_threshold_crit} dBm)",
            )
            count += 1

            # TODO: SMS/Email alert পাঠানো (billing module তৈরি হলে)
            logger.warning(
                f"Critical ONU signal: {onu.serial_number} @ {onu.olt.name} "
                f"RX={onu.rx_power} dBm"
            )

    return {'critical_onus_detected': count}
