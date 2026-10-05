# ফাইল: backend/apps/accounting/tasks.py
# Accounting-এর background Celery tasks।

import logging
from datetime import date
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def close_daily_account_task(self):
    """
    প্রতিরাত ১১:৫৯-এ আজকের হিসাব auto-close করা।
    Income + Payment - Expense = Net Profit।
    """
    from apps.accounting.services import DailyAccountService
    today  = date.today()
    try:
        daily = DailyAccountService.close_day(today)
        logger.info(f"Auto day close: {today} | Net={daily.net_profit_loss}")
        return {'date': str(today), 'net': float(daily.net_profit_loss)}
    except Exception as exc:
        logger.error(f"Day close failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True)
def update_account_balances_task(self, month_str: str = None):
    """
    মাসিক account balance snapshot আপডেট করা।
    Trial Balance ও reports দ্রুত তৈরির জন্য।
    """
    from apps.accounting.models import Account, AccountBalance, TransactionLine
    from django.db.models import Sum
    from dateutil.relativedelta import relativedelta

    today       = date.today()
    month_start = date.fromisoformat(month_str + '-01') if month_str else today.replace(day=1)

    accounts = Account.objects.filter(is_active=True, is_group=False)
    updated  = 0

    for acc in accounts:
        lines = TransactionLine.objects.filter(
            account=acc,
            journal__is_posted=True,
            journal__date__gte=month_start,
            journal__date__lt=month_start + relativedelta(months=1),
        )
        dr = lines.filter(type='debit').aggregate(t=Sum('amount'))['t'] or 0
        cr = lines.filter(type='credit').aggregate(t=Sum('amount'))['t'] or 0

        if dr == 0 and cr == 0:
            continue

        AccountBalance.objects.update_or_create(
            account=acc,
            period_month=month_start,
            defaults={
                'total_debit':  dr,
                'total_credit': cr,
            }
        )
        updated += 1

    logger.info(f"Account balances updated: {updated} accounts for {month_start}")
    return {'updated': updated, 'month': str(month_start)}
