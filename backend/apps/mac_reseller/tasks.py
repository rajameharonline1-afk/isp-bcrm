# ফাইল: backend/apps/mac_reseller/tasks.py
# এই ফাইলটি Payment Gateway (PGW) payment sync-এর Celery background tasks ধারণ করে।

import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def expire_stale_pgw_payments_task(self):
    """
    দীর্ঘ সময় (৩০ মিনিট+) ধরে 'pending' থাকা PGW payment গুলো 'failed' করা।
    Gateway callback না এলে payment আর valid নয় — এই task সেগুলো mark করে।
    """
    from apps.mac_reseller.models import ClientPGWPayment

    # ৩০ মিনিটের বেশি পুরনো pending payment গুলো
    cutoff  = timezone.now() - timedelta(minutes=30)
    expired = ClientPGWPayment.objects.filter(
        status=ClientPGWPayment.PGWStatus.PENDING,
        created_at__lt=cutoff,
    )
    count   = expired.update(
        status=ClientPGWPayment.PGWStatus.FAILED,
        note='Auto-expired: no gateway callback received within 30 minutes.',
        updated_at=timezone.now(),
    )
    logger.info("Stale PGW payments expired: %d", count)
    return {'expired_count': count, 'cutoff': str(cutoff)}


@shared_task(bind=True)
def sync_pending_pgw_payments_task(self):
    """
    ১০–৩০ মিনিট বয়সী 'pending' payment-এর status gateway-এ query করে আপডেট করা।
    Webhook miss হলে এই task সেটি ধরে ফেলে।
    Gateway-ভেদে logic আলাদা; unsupported gateway হলে skip করা হয়।
    """
    from apps.mac_reseller.models import ClientPGWPayment
    from apps.mac_reseller.services import PGWPaymentService

    now         = timezone.now()
    window_start = now - timedelta(minutes=30)
    window_end   = now - timedelta(minutes=10)

    payments = ClientPGWPayment.objects.filter(
        status=ClientPGWPayment.PGWStatus.PENDING,
        created_at__range=(window_start, window_end),
    ).exclude(order_id='')

    confirmed = failed = skipped = 0
    for payment in payments:
        try:
            result = _query_gateway_status(payment)
            if result == 'success':
                PGWPaymentService.confirm_payment(
                    order_id           = payment.order_id,
                    pgw_transaction_id = payment.pgw_transaction_id or '',
                    gateway_response   = {'source': 'auto_sync'},
                )
                confirmed += 1
            elif result == 'failed':
                PGWPaymentService.fail_payment(
                    order_id = payment.order_id,
                    reason   = 'Gateway sync: payment not completed.',
                )
                failed += 1
            else:
                skipped += 1
        except Exception as exc:
            logger.error("PGW sync error for order %s: %s", payment.order_id, exc)
            skipped += 1

    logger.info("PGW sync: confirmed=%d failed=%d skipped=%d", confirmed, failed, skipped)
    return {'confirmed': confirmed, 'failed': failed, 'skipped': skipped}


def _query_gateway_status(payment) -> str:
    """
    নির্দিষ্ট gateway-এ payment-এর বর্তমান status query করে।
    'success', 'failed', 'pending' ফেরত দেয়।
    Unsupported gateway-এ 'pending' ফেরত দেয় — manual verify দরকার।
    """
    from apps.system_config.models import PaymentGateway as GWConfig

    try:
        gw_config = GWConfig.objects.get(provider=payment.gateway, is_active=True)
    except GWConfig.DoesNotExist:
        # Gateway configured নেই — skip
        return 'pending'

    if payment.gateway == 'sslcommerz':
        return _check_sslcommerz(payment, gw_config)
    # bKash, Nagad ইত্যাদির জন্য তাদের নিজস্ব SDK/API integration প্রয়োজন
    # সেগুলো যোগ করার আগ পর্যন্ত pending হিসেবে রাখা হচ্ছে
    return 'pending'


def _check_sslcommerz(payment, gw_config) -> str:
    """
    SSL Commerz-এর Order Validation API দিয়ে payment status check।
    Sandbox ও live উভয় mode support করে।
    """
    import requests

    base_url = (
        'https://sandbox.sslcommerz.com' if gw_config.is_sandbox
        else 'https://securepay.sslcommerz.com'
    )
    url = f"{base_url}/validator/api/validationserverAPI.php"
    params = {
        'val_id'     : payment.pgw_transaction_id,
        'store_id'   : gw_config.store_id,
        'store_passwd': gw_config.store_password,
        'format'     : 'json',
    }
    try:
        resp   = requests.get(url, params=params, timeout=15)
        data   = resp.json()
        status = data.get('status', '').upper()
        if status == 'VALID':
            return 'success'
        if status in ('FAILED', 'CANCELLED', 'UNATTEMPTED', 'EXPIRED'):
            return 'failed'
    except Exception as exc:
        logger.warning("SSL Commerz status check error: %s", exc)
    return 'pending'


@shared_task(bind=True)
def generate_reseller_balance_report_task(self):
    """
    প্রতিদিন সব active reseller-এর balance snapshot তৈরি করা।
    Dashboard-এ দ্রুত data দেখানোর জন্য।
    """
    from apps.mac_reseller.models import MACReseller

    resellers = MACReseller.objects.filter(status=MACReseller.ResellerStatus.ACTIVE)
    report    = [
        {'id': r.id, 'name': r.name, 'balance': float(r.balance)}
        for r in resellers
    ]
    logger.info("Reseller balance snapshot: %d resellers", len(report))
    return {'resellers': len(report), 'snapshot': report}
