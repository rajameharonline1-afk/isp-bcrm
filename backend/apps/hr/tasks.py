# ফাইল: backend/apps/hr/tasks.py
# HR-এর background Celery tasks — payroll auto-generate, attendance reminder।

import logging
from datetime import date
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def auto_generate_monthly_payroll_task(self):
    """
    প্রতি মাসের ১ তারিখে payroll auto-generate করা।
    Celery Beat-এ মাসের প্রথম দিন চালানো হবে।
    """
    from apps.hr.services import PayrollService
    today = date.today()
    if today.day != 1:
        return {'skipped': True, 'reason': 'Not 1st of month'}

    payroll, created, skipped = PayrollService.generate_payroll(month=today)
    logger.info(f"Auto payroll generated: {payroll}, created={created}, skipped={len(skipped)}")
    return {
        'payroll_id': payroll.id,
        'month':      str(today),
        'created':    created,
        'skipped_count': len(skipped),
    }


@shared_task(bind=True)
def mark_absent_unmarked_employees_task(self):
    """
    প্রতিদিন attendance না দেওয়া active কর্মচারীদের Absent mark করা।
    রাত ১১টায় চালানো হয় যাতে যারা manually mark হয়নি তাদের absent ধরা যায়।
    """
    from apps.hr.models import Employee, Attendance

    today     = date.today()
    employees = Employee.objects.filter(status=Employee.Status.ACTIVE)
    marked    = 0

    for emp in employees:
        _, created = Attendance.objects.get_or_create(
            employee=emp,
            date=today,
            defaults={'status': Attendance.AttendanceStatus.ABSENT},
        )
        if created:
            marked += 1

    logger.info(f"Absent marked for {marked} employees on {today}")
    return {'marked': marked, 'date': str(today)}
