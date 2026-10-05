# ফাইল: backend/apps/billing/services.py
# Billing-এর সব business logic এখানে।
# Auto bill generation, payment collection, due tracking সব এখানে।

import logging
from datetime import date
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from django.db import transaction

logger = logging.getLogger(__name__)


class BillingService:
    """
    Billing ও Payment-এর সব business logic।
    প্রতি মাসে automatic bill generate করা ও payment collect করা।
    """

    @staticmethod
    @transaction.atomic
    def generate_bill_for_client(client, bill_month: date, generated_by=None) -> tuple:
        """
        একটি client-এর জন্য নির্দিষ্ট মাসের বিল তৈরি করা।
        Return: (billing_instance, created_bool)
        """
        from apps.billing.models import Billing
        from apps.clients.models import Client

        # এই মাসের বিল ইতিমধ্যে আছে কিনা চেক করা
        month_start = bill_month.replace(day=1)
        existing    = Billing.objects.filter(client=client, bill_month=month_start).first()
        if existing:
            return existing, False

        payable = client.payable_amount  # monthly_bill - discount

        # Due date = client-এর expiry_date (এই মাসে)
        try:
            due_date = month_start.replace(day=client.bill_date) + relativedelta(days=client.expiry_day)
        except ValueError:
            import calendar
            last_day = calendar.monthrange(month_start.year, month_start.month)[1]
            due_date = month_start.replace(day=min(client.bill_date, last_day)) + relativedelta(days=client.expiry_day)

        billing = Billing.objects.create(
            client=client,
            bill_month=month_start,
            bill_amount=client.monthly_bill,
            discount=client.discount,
            payable_amount=payable,
            paid_amount=Decimal('0'),
            due_amount=payable,
            bill_date=date.today(),
            due_date=due_date,
            status=Billing.BillStatus.UNPAID,
            generated_by=generated_by,
        )

        # Client-এর due_amount আপডেট করা
        client.due_amount = Decimal(str(client.due_amount)) + payable
        client.payment_status = 'unpaid'
        client.save(update_fields=['due_amount', 'payment_status', 'updated_at'])

        logger.info(f"Bill generated: {client.username} month={month_start} amount={payable}")
        return billing, True

    @staticmethod
    @transaction.atomic
    def collect_payment(client, amount: Decimal, method: str,
                        billing=None, transaction_id='',
                        collected_by=None, note='') -> dict:
        """
        Client-এর payment collect করা।
        Advance balance handle করা, billing status আপডেট করা।
        """
        from apps.billing.models import Billing, Payment
        from apps.clients.models import Client

        amount = Decimal(str(amount))

        # Payment record তৈরি করা
        payment = Payment.objects.create(
            client=client,
            billing=billing,
            amount=amount,
            method=method,
            transaction_id=transaction_id,
            collected_by=collected_by,
            note=note,
        )

        remaining = amount

        # Billing-এ apply করা (oldest unpaid first)
        if billing:
            unpaid_bills = [billing]
        else:
            unpaid_bills = Billing.objects.filter(
                client=client,
                status__in=[Billing.BillStatus.UNPAID, Billing.BillStatus.PARTIAL, Billing.BillStatus.OVERDUE],
            ).order_by('bill_month')

        for bill in unpaid_bills:
            if remaining <= 0:
                break
            apply      = min(remaining, bill.due_amount)
            bill.paid_amount += apply
            bill.due_amount  -= apply
            remaining  -= apply

            if bill.due_amount <= 0:
                bill.status = Billing.BillStatus.PAID
            else:
                bill.status = Billing.BillStatus.PARTIAL
            bill.save(update_fields=['paid_amount', 'due_amount', 'status', 'updated_at'])

        # Remaining amount advance balance-এ যোগ করা
        if remaining > 0:
            client.advance_balance = Decimal(str(client.advance_balance)) + remaining
            logger.info(f"Advance added: {client.username} +{remaining} BDT")

        # Client-এর total due re-calculate করা
        from django.db.models import Sum
        total_due = Billing.objects.filter(
            client=client,
            status__in=[Billing.BillStatus.UNPAID, Billing.BillStatus.PARTIAL, Billing.BillStatus.OVERDUE],
        ).aggregate(t=Sum('due_amount'))['t'] or Decimal('0')

        client.due_amount     = total_due
        client.payment_status = BillingService._get_payment_status(client)
        client.save(update_fields=['due_amount', 'advance_balance', 'payment_status', 'updated_at'])

        logger.info(f"Payment collected: {client.username} amount={amount} method={method}")
        return {
            'success':    True,
            'payment_id': payment.id,
            'amount':     str(amount),
            'method':     method,
            'remaining_due': str(client.due_amount),
            'advance_balance': str(client.advance_balance),
        }

    @staticmethod
    def _get_payment_status(client) -> str:
        """Client-এর payment status calculate করা।"""
        from apps.clients.models import Client
        from apps.billing.models import Billing

        if client.due_amount <= 0 and client.advance_balance > 0:
            return Client.PaymentStatus.PAID
        if client.due_amount <= 0:
            return Client.PaymentStatus.PAID

        # Overdue check
        overdue_bill = Billing.objects.filter(
            client=client,
            due_date__lt=date.today(),
            status__in=[Billing.BillStatus.UNPAID, Billing.BillStatus.PARTIAL],
        ).exists()
        if overdue_bill:
            return Client.PaymentStatus.OVERDUE

        # Partial
        partial = Billing.objects.filter(
            client=client,
            status=Billing.BillStatus.PARTIAL,
        ).exists()
        return Client.PaymentStatus.PARTIAL if partial else Client.PaymentStatus.UNPAID

    @staticmethod
    def auto_generate_monthly_bills(target_date: date = None, generated_by=None) -> dict:
        """
        আজকের bill_date যে সব client-এর, তাদের সবার বিল generate করা।
        Celery Beat প্রতিদিন একবার এই function call করে।
        """
        from apps.clients.models import Client
        from apps.billing.models import Billing

        today      = target_date or date.today()
        bill_day   = today.day
        month_start = today.replace(day=1)

        # আজকে যাদের bill_date সেই সব active client
        clients = Client.objects.filter(
            status=Client.Status.ACTIVE,
            bill_date=bill_day,
        ).select_related('package')

        generated = 0
        skipped   = 0
        errors    = 0

        for client in clients:
            try:
                _, created = BillingService.generate_bill_for_client(
                    client=client,
                    bill_month=month_start,
                    generated_by=generated_by,
                )
                if created:
                    generated += 1
                else:
                    skipped += 1
            except Exception as exc:
                errors += 1
                logger.error(f"Bill generation failed for {client.username}: {exc}")

        result = {'generated': generated, 'skipped': skipped, 'errors': errors, 'date': str(today)}
        logger.info(f"Auto bill generation: {result}")
        return result


def models_sum(field):
    """Django Sum aggregate shortcut।"""
    from django.db.models import Sum
    return Sum(field)
