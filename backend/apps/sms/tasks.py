# ফাইল: backend/apps/sms/tasks.py
# এই ফাইলটি SMS পাঠানোর Celery background task ধারণ করে।

import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_sms_task(self, message_id):
    """একটি pending SMS gateway-তে পাঠায়; ব্যর্থ হলে ৬০ সেকেন্ড পর আবার চেষ্টা করে।"""
    from .models import SMSMessage
    from .services import SMSService

    sms = SMSMessage.objects.select_related('gateway').filter(pk=message_id).first()
    if sms is None or sms.status == SMSMessage.Status.SENT:
        return {'skipped': True}

    if SMSService.deliver(sms):
        return {'sent': message_id}
    if self.request.retries < self.max_retries:
        raise self.retry()
    logger.error('SMS %s failed after retries: %s', message_id, sms.response)
    return {'failed': message_id}
