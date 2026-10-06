# ফাইল: backend/apps/mac_reseller/services.py
# এই ফাইলটি MAC Reseller-সংক্রান্ত business logic service functions ধারণ করে।

import uuid
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from .models import (
    MACReseller, MACResellerFunding, ClientPGWPayment,
    PGWTransactionSettlement,
)

logger = logging.getLogger(__name__)


class MACResellerFundingService:
    """Reseller account balance ও funding পরিচালনার service।"""

    @staticmethod
    @transaction.atomic
    def approve_funding(funding_id: int, approved_by) -> MACResellerFunding:
        """
        Funding request approve করে reseller-এর balance বাড়ায়।
        Balance update এবং funding record উভয় atomic transaction-এ হয়।
        """
        # select_for_update দিয়ে row lock করা হচ্ছে, যাতে concurrent update না হয়
        funding = MACResellerFunding.objects.select_for_update().get(pk=funding_id)

        if funding.status != MACResellerFunding.FundingStatus.PENDING:
            raise ValueError(f"শুধুমাত্র 'pending' funding approve করা যাবে (বর্তমান: {funding.status})।")

        reseller = MACReseller.objects.select_for_update().get(pk=funding.reseller_id)

        # Balance update
        balance_before         = reseller.balance
        reseller.balance       += funding.amount
        reseller.save(update_fields=['balance', 'updated_at'])

        # Funding record update
        funding.status         = MACResellerFunding.FundingStatus.APPROVED
        funding.balance_before = balance_before
        funding.balance_after  = reseller.balance
        funding.approved_by    = approved_by
        funding.approved_at    = timezone.now()
        funding.save()

        logger.info(
            "Funding approved: reseller=%s amount=%s balance=%s→%s",
            reseller.name, funding.amount, balance_before, reseller.balance
        )
        return funding

    @staticmethod
    @transaction.atomic
    def reject_funding(funding_id: int, rejected_by) -> MACResellerFunding:
        """Funding request reject করে।"""
        funding = MACResellerFunding.objects.select_for_update().get(pk=funding_id)

        if funding.status != MACResellerFunding.FundingStatus.PENDING:
            raise ValueError(f"শুধুমাত্র 'pending' funding reject করা যাবে।")

        funding.status      = MACResellerFunding.FundingStatus.REJECTED
        funding.approved_by = rejected_by
        funding.approved_at = timezone.now()
        funding.save()

        return funding

    @staticmethod
    @transaction.atomic
    def deduct_balance(reseller: MACReseller, amount: Decimal, reason: str = '') -> None:
        """
        Reseller-এর balance থেকে নির্দিষ্ট পরিমাণ কাটা।
        Package activation বা অন্যান্য charge-এ ব্যবহার হয়।
        """
        reseller_locked = MACReseller.objects.select_for_update().get(pk=reseller.pk)
        if reseller_locked.balance < amount:
            raise ValueError(
                f"অপর্যাপ্ত balance। প্রয়োজন: {amount}৳, বর্তমান: {reseller_locked.balance}৳"
            )
        reseller_locked.balance -= amount
        reseller_locked.save(update_fields=['balance', 'updated_at'])
        logger.info("Balance deducted: reseller=%s amount=%s reason=%s", reseller.name, amount, reason)


class PGWPaymentService:
    """Payment Gateway payment পরিচালনার service।"""

    @staticmethod
    def generate_order_id() -> str:
        """Unique order ID তৈরি করে।"""
        return f"PGW-{uuid.uuid4().hex[:12].upper()}"

    @staticmethod
    @transaction.atomic
    def create_payment(
        client,
        billing,
        amount: Decimal,
        gateway: str,
        reseller=None,
        processing_fee: Decimal = Decimal('0'),
    ) -> ClientPGWPayment:
        """
        নতুন PGW payment তৈরি করে (প্রাথমিক status: pending)।
        Payment Gateway-এ redirect করার আগে এই entry তৈরি হয়।
        """
        payment = ClientPGWPayment.objects.create(
            client         = client,
            billing        = billing,
            reseller       = reseller,
            amount         = amount,
            gateway        = gateway,
            processing_fee = processing_fee,
            order_id       = PGWPaymentService.generate_order_id(),
            status         = ClientPGWPayment.PGWStatus.PENDING,
        )
        return payment

    @staticmethod
    @transaction.atomic
    def confirm_payment(order_id: str, pgw_transaction_id: str, gateway_response: dict) -> ClientPGWPayment:
        """
        Gateway-এর callback/webhook পেলে payment confirm করা হয়।
        Payment-এর billing-ও update হয় যদি billing linked থাকে।
        """
        payment = ClientPGWPayment.objects.select_for_update().get(order_id=order_id)

        if payment.status != ClientPGWPayment.PGWStatus.PENDING:
            # Duplicate callback এলে idempotent response দিতে হবে
            return payment

        payment.pgw_transaction_id = pgw_transaction_id
        payment.gateway_response   = gateway_response
        payment.status             = ClientPGWPayment.PGWStatus.SUCCESS
        payment.payment_date       = timezone.now()
        payment.save()

        # Billing update
        if payment.billing:
            from apps.billing.services import BillingService
            BillingService.collect_payment(
                client       = payment.client,
                billing_id   = payment.billing_id,
                amount       = payment.net_amount,
                method       = 'online',
                transaction_id = pgw_transaction_id,
                note         = f"PGW: {payment.gateway} | Order: {order_id}",
                collected_by = None,
            )

        logger.info("PGW payment confirmed: order=%s txn=%s amount=%s", order_id, pgw_transaction_id, payment.amount)
        return payment

    @staticmethod
    @transaction.atomic
    def fail_payment(order_id: str, reason: str = '') -> ClientPGWPayment:
        """Payment fail হলে status update।"""
        payment = ClientPGWPayment.objects.select_for_update().get(order_id=order_id)
        if payment.status == ClientPGWPayment.PGWStatus.PENDING:
            payment.status = ClientPGWPayment.PGWStatus.FAILED
            payment.note   = reason
            payment.save()
        return payment


class SettlementService:
    """PGW Transaction Settlement পরিচালনার service।"""

    @staticmethod
    @transaction.atomic
    def create_settlement(reseller_id: int, payment_ids: list, settlement_date, note: str, settled_by) -> PGWTransactionSettlement:
        """
        নির্দিষ্ট payments-এর জন্য settlement তৈরি করে।
        সব payment-এর amount যোগ করে net settlement calculate করা হয়।
        """
        reseller = MACReseller.objects.get(pk=reseller_id)
        payments = ClientPGWPayment.objects.filter(
            pk__in=payment_ids,
            status=ClientPGWPayment.PGWStatus.SUCCESS,
        )

        if not payments.exists():
            raise ValueError("কোনো valid payment পাওয়া যায়নি।")

        # Total calculation
        total_amount = sum(p.amount for p in payments)
        total_fee    = sum(p.processing_fee for p in payments)
        net_amount   = total_amount - total_fee

        settlement = PGWTransactionSettlement.objects.create(
            reseller        = reseller,
            payment_count   = payments.count(),
            total_amount    = total_amount,
            total_fee       = total_fee,
            net_settlement  = net_amount,
            settlement_date = settlement_date,
            status          = PGWTransactionSettlement.SettlementStatus.PENDING,
            note            = note,
            settled_by      = settled_by,
        )
        settlement.payments.set(payments)

        logger.info(
            "Settlement created: reseller=%s payments=%d net=%s",
            reseller.name, payments.count(), net_amount
        )
        return settlement

    @staticmethod
    @transaction.atomic
    def complete_settlement(settlement_id: int, settled_by) -> PGWTransactionSettlement:
        """Settlement সম্পন্ন করে।"""
        settlement = PGWTransactionSettlement.objects.select_for_update().get(pk=settlement_id)

        if settlement.status == PGWTransactionSettlement.SettlementStatus.COMPLETED:
            raise ValueError("এই settlement ইতিমধ্যে সম্পন্ন হয়েছে।")

        settlement.status     = PGWTransactionSettlement.SettlementStatus.COMPLETED
        settlement.settled_by = settled_by
        settlement.settled_at = timezone.now()
        settlement.save()

        return settlement
