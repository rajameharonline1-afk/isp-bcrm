# ফাইল: backend/apps/reports/tasks.py
# এই ফাইলটি বিভিন্ন ধরনের report auto-generate করার Celery tasks ধারণ করে।

import logging
from datetime import date
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def generate_daily_collection_report_task(self):
    """
    প্রতিদিন রাত ১১:৩০-এ আজকের bill collection report তৈরি।
    আজকের মোট payment, method-ভেদে breakdown, collector-ভেদে summary।
    """
    from django.db.models import Sum, Count
    from apps.billing.models import Payment

    today  = date.today()
    result = (
        Payment.objects.filter(payment_date__date=today)
        .values('method')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total')
    )
    summary = list(result)
    grand_total = sum(r['total'] for r in summary if r['total'])

    logger.info("Daily collection report: %s | Total=%s", today, grand_total)
    return {
        'date'        : str(today),
        'grand_total' : float(grand_total),
        'breakdown'   : [
            {'method': r['method'], 'total': float(r['total']), 'count': r['count']}
            for r in summary
        ],
    }


@shared_task(bind=True)
def generate_due_customer_report_task(self):
    """
    সাপ্তাহিক due customer তালিকা তৈরি।
    Due amount, expiry date ও package সহ export করার জন্য।
    """
    from apps.clients.models import Client

    due_clients = Client.objects.filter(
        status=Client.Status.ACTIVE,
        due_amount__gt=0,
    ).select_related('package', 'zone').values(
        'id', 'full_name', 'username', 'phone',
        'due_amount', 'expiry_date',
        'package__name', 'zone__name',
    ).order_by('-due_amount')[:500]

    data = list(due_clients)
    logger.info("Due customer report: %d clients", len(data))
    return {'total_due_clients': len(data), 'clients': data}


@shared_task(bind=True)
def generate_monthly_btrc_report_task(self):
    """
    প্রতি মাসে BTRC-এ জমা দেওয়ার জন্য monthly report তৈরি।
    মোট সক্রিয় সংযোগ, protocol-ভেদে breakdown, জেলা-ভেদে count।
    BTRC (Bangladesh Telecommunication Regulatory Commission) নির্দেশিকা অনুযায়ী।
    """
    from django.db.models import Count
    from apps.clients.models import Client

    today = date.today()
    # গত মাসের data
    if today.month == 1:
        report_month = today.replace(year=today.year - 1, month=12, day=1)
    else:
        report_month = today.replace(month=today.month - 1, day=1)

    active_clients = Client.objects.filter(status=Client.Status.ACTIVE)
    total_active   = active_clients.count()

    # Protocol-ভেদে ভাঙন
    by_protocol = list(
        active_clients.values('protocol__name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    # জেলা-ভেদে ভাঙন
    by_district = list(
        active_clients.filter(district__isnull=False)
        .values('district__name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    report = {
        'report_month' : str(report_month),
        'generated_at' : str(today),
        'total_active' : total_active,
        'by_protocol'  : by_protocol,
        'by_district'  : by_district,
    }
    logger.info("BTRC monthly report generated: %s | Active=%d", report_month, total_active)
    return report


@shared_task(bind=True)
def generate_monthly_financial_summary_task(self):
    """
    মাসিক আর্থিক সারসংক্ষেপ তৈরি।
    মোট income, expense, bill collection ও net profit summary।
    """
    from django.db.models import Sum
    from apps.billing.models import Payment
    from apps.income.models import DailyIncome
    from apps.expense.models import DailyExpense

    today        = date.today()
    month_start  = today.replace(day=1)
    # গত মাস
    if today.month == 1:
        last_month_start = today.replace(year=today.year - 1, month=12, day=1)
    else:
        last_month_start = today.replace(month=today.month - 1, day=1)

    # এই মাসের payment
    payments_this = Payment.objects.filter(
        payment_date__date__gte=month_start,
        payment_date__date__lte=today,
    ).aggregate(total=Sum('amount'))['total'] or 0

    # এই মাসের income
    income_this = DailyIncome.objects.filter(
        date__gte=month_start,
        date__lte=today,
    ).aggregate(total=Sum('amount'))['total'] or 0

    # এই মাসের expense
    expense_this = DailyExpense.objects.filter(
        date__gte=month_start,
        date__lte=today,
    ).aggregate(total=Sum('amount'))['total'] or 0

    net_profit = float(income_this) - float(expense_this)

    summary = {
        'month'             : str(month_start),
        'bill_collection'   : float(payments_this),
        'total_income'      : float(income_this),
        'total_expense'     : float(expense_this),
        'net_profit'        : net_profit,
        'generated_at'      : str(today),
    }
    logger.info("Monthly financial summary: %s | Net=%s", month_start, net_profit)
    return summary


@shared_task(bind=True)
def generate_discount_report_task(self):
    """
    মাসিক discount report — কোন client কত discount পেয়েছে।
    Financial audit-এর জন্য দরকারি।
    """
    from django.db.models import Sum
    from apps.billing.models import Billing

    today       = date.today()
    month_start = today.replace(day=1)

    discounts = (
        Billing.objects.filter(
            bill_month__gte=month_start,
            discount__gt=0,
        )
        .select_related('client')
        .values('client__username', 'client__full_name', 'bill_month', 'discount')
        .order_by('-discount')[:200]
    )
    data         = list(discounts)
    total_discount = Billing.objects.filter(
        bill_month__gte=month_start, discount__gt=0,
    ).aggregate(t=Sum('discount'))['t'] or 0

    logger.info("Discount report: %d records | Total=%s", len(data), total_discount)
    return {
        'month'          : str(month_start),
        'total_discount' : float(total_discount),
        'records'        : len(data),
        'data'           : data,
    }
