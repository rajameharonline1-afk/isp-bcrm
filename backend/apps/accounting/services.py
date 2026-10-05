# ফাইল: backend/apps/accounting/services.py
# Accounting module-এর সব business logic।
# Journal posting, Balance Sheet, P&L, Trial Balance, Cash Book সব এখানে।

import logging
from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone

from .models import Account, AccountType, JournalEntry, TransactionLine, AccountBalance

logger = logging.getLogger(__name__)

# ===== System Account Codes (পরিবর্তন করা যাবে না) =====
ACCOUNTS_RECEIVABLE_CODE = '1100'   # Accounts Receivable (Client due)
CASH_IN_HAND_CODE        = '1001'   # Cash in Hand
BKASH_ACCOUNT_CODE       = '1010'   # bKash Account
NAGAD_ACCOUNT_CODE       = '1011'   # Nagad Account
BANK_ACCOUNT_CODE        = '1020'   # Bank Account
INCOME_ISP_CODE          = '4001'   # ISP Service Income
INCOME_CONNECTION_CODE   = '4002'   # Connection Fee Income
EXPENSE_SALARY_CODE      = '5001'   # Salary Expense
EXPENSE_OFFICE_CODE      = '5010'   # Office & Admin Expense
RETAINED_EARNINGS_CODE   = '3100'   # Retained Earnings


class JournalService:
    """
    Journal Entry তৈরি ও post করার service।
    Double-entry system enforce করে।
    """

    @staticmethod
    @transaction.atomic
    def create_journal(date_val: date, description: str, lines: list,
                       entry_type: str = JournalEntry.EntryType.MANUAL,
                       reference: str = '', reference_model: str = '',
                       reference_id: int = None, created_by=None,
                       auto_post: bool = False) -> JournalEntry:
        """
        নতুন Journal Entry তৈরি করা।
        lines = [{'account_code': '1001', 'type': 'debit', 'amount': 1000, 'desc': '...'}, ...]
        Debit total = Credit total হওয়া বাধ্যতামূলক।
        """
        # Line validation
        total_debit  = sum(Decimal(str(l['amount'])) for l in lines if l['type'] == 'debit')
        total_credit = sum(Decimal(str(l['amount'])) for l in lines if l['type'] == 'credit')

        if abs(total_debit - total_credit) > Decimal('0.01'):
            raise ValueError(
                f"Journal not balanced: Debit={total_debit} Credit={total_credit}"
            )

        journal = JournalEntry.objects.create(
            date=date_val,
            description=description,
            entry_type=entry_type,
            reference=reference,
            reference_model=reference_model,
            reference_id=reference_id,
            created_by=created_by,
        )

        for line in lines:
            account = Account.objects.get(code=line['account_code'])
            TransactionLine.objects.create(
                journal=journal,
                account=account,
                type=line['type'],
                amount=Decimal(str(line['amount'])),
                description=line.get('desc', ''),
            )

        if auto_post:
            JournalService.post_journal(journal, posted_by=created_by)

        logger.info(f"Journal created: {journal.entry_no} | {description}")
        return journal

    @staticmethod
    @transaction.atomic
    def post_journal(journal: JournalEntry, posted_by=None):
        """
        Journal Entry post করা — এরপর আর edit করা যাবে না।
        Account balance update হবে।
        """
        if journal.is_posted:
            raise ValueError("Journal already posted")
        if not journal.is_balanced:
            raise ValueError("Cannot post unbalanced journal")

        journal.is_posted = True
        journal.posted_by = posted_by
        journal.posted_at = timezone.now()
        journal.save(update_fields=['is_posted', 'posted_by', 'posted_at'])

        logger.info(f"Journal posted: {journal.entry_no}")
        return journal

    # =========================================================
    # Auto Journal Creation (system-generated entries)
    # =========================================================

    @staticmethod
    def post_payment_journal(payment, posted_by=None):
        """
        Client payment collect হলে auto journal entry তৈরি করা।
        Dr: Cash/bKash/Bank   Cr: Accounts Receivable
        """
        method_account_map = {
            'cash':   CASH_IN_HAND_CODE,
            'bkash':  BKASH_ACCOUNT_CODE,
            'nagad':  NAGAD_ACCOUNT_CODE,
            'rocket': BKASH_ACCOUNT_CODE,  # bKash-এ pool করা
            'bank':   BANK_ACCOUNT_CODE,
            'online': BANK_ACCOUNT_CODE,
            'advance': CASH_IN_HAND_CODE,
        }
        debit_account = method_account_map.get(payment.method, CASH_IN_HAND_CODE)

        try:
            return JournalService.create_journal(
                date_val=payment.payment_date,
                description=f"Payment from {payment.client.username} | {payment.method}",
                entry_type=JournalEntry.EntryType.PAYMENT,
                reference=str(payment.transaction_id or payment.id),
                reference_model='payment',
                reference_id=payment.id,
                created_by=posted_by,
                auto_post=True,
                lines=[
                    {'account_code': debit_account,          'type': 'debit',  'amount': payment.amount},
                    {'account_code': ACCOUNTS_RECEIVABLE_CODE, 'type': 'credit', 'amount': payment.amount},
                ],
            )
        except Account.DoesNotExist:
            logger.warning(f"Account not found for payment journal. Skipping auto-journal.")
            return None

    @staticmethod
    def post_income_journal(income, posted_by=None):
        """
        Income record হলে auto journal।
        Dr: Cash/bKash   Cr: Income Account
        """
        method_account_map = {
            'cash': CASH_IN_HAND_CODE, 'bkash': BKASH_ACCOUNT_CODE,
            'nagad': NAGAD_ACCOUNT_CODE, 'bank': BANK_ACCOUNT_CODE,
        }
        debit_code = method_account_map.get(income.method, CASH_IN_HAND_CODE)

        # Income category-র account code নেওয়া
        credit_code = income.category.account_code or INCOME_ISP_CODE

        try:
            return JournalService.create_journal(
                date_val=income.date,
                description=f"Income: {income.category.name} | {income.description[:50]}",
                entry_type=JournalEntry.EntryType.INCOME,
                reference_model='income',
                reference_id=income.id,
                created_by=posted_by,
                auto_post=True,
                lines=[
                    {'account_code': debit_code,   'type': 'debit',  'amount': income.amount},
                    {'account_code': credit_code,  'type': 'credit', 'amount': income.amount},
                ],
            )
        except Account.DoesNotExist:
            logger.warning(f"Account not found for income journal. Skipping.")
            return None

    @staticmethod
    def post_expense_journal(expense, posted_by=None):
        """
        Expense record হলে auto journal।
        Dr: Expense Account   Cr: Cash/Bank
        """
        method_account_map = {
            'cash': CASH_IN_HAND_CODE, 'bkash': BKASH_ACCOUNT_CODE,
            'nagad': NAGAD_ACCOUNT_CODE, 'bank': BANK_ACCOUNT_CODE,
        }
        credit_code = method_account_map.get(expense.method, CASH_IN_HAND_CODE)
        debit_code  = expense.category.account_code or EXPENSE_OFFICE_CODE

        try:
            return JournalService.create_journal(
                date_val=expense.date,
                description=f"Expense: {expense.category.name} | {expense.description[:50]}",
                entry_type=JournalEntry.EntryType.EXPENSE,
                reference_model='expense',
                reference_id=expense.id,
                created_by=posted_by,
                auto_post=True,
                lines=[
                    {'account_code': debit_code,  'type': 'debit',  'amount': expense.amount},
                    {'account_code': credit_code, 'type': 'credit', 'amount': expense.amount},
                ],
            )
        except Account.DoesNotExist:
            logger.warning(f"Account not found for expense journal. Skipping.")
            return None


class ReportService:
    """
    Financial reports তৈরির service।
    Trial Balance, Balance Sheet, P&L, Cash Book সব এখানে।
    """

    @staticmethod
    def get_trial_balance(from_date: date, to_date: date) -> list:
        """
        Trial Balance — সব account-এর debit/credit summary।
        Return: [{account_code, account_name, type, debit, credit, balance}, ...]
        """
        accounts = Account.objects.filter(
            is_active=True, is_group=False,
        ).select_related('account_type').order_by('code')

        result = []
        for acc in accounts:
            lines = TransactionLine.objects.filter(
                account=acc,
                journal__is_posted=True,
                journal__date__gte=from_date,
                journal__date__lte=to_date,
            )
            debit  = lines.filter(type='debit').aggregate(t=Sum('amount'))['t'] or Decimal('0')
            credit = lines.filter(type='credit').aggregate(t=Sum('amount'))['t'] or Decimal('0')

            if debit == 0 and credit == 0 and acc.opening_balance == 0:
                continue

            if acc.account_type.nature == 'debit':
                balance = acc.opening_balance + debit - credit
            else:
                balance = acc.opening_balance + credit - debit

            result.append({
                'account_code':  acc.code,
                'account_name':  acc.name,
                'account_type':  acc.account_type.name,
                'nature':        acc.account_type.nature,
                'opening':       float(acc.opening_balance),
                'total_debit':   float(debit),
                'total_credit':  float(credit),
                'closing':       float(balance),
            })

        return result

    @staticmethod
    def get_profit_loss(from_date: date, to_date: date) -> dict:
        """
        Profit & Loss Statement।
        Income - Expense = Net Profit/Loss।
        """
        income_types  = AccountType.objects.filter(name__icontains='income')
        expense_types = AccountType.objects.filter(name__icontains='expense')

        income_accounts  = Account.objects.filter(account_type__in=income_types, is_active=True, is_group=False)
        expense_accounts = Account.objects.filter(account_type__in=expense_types, is_active=True, is_group=False)

        def get_account_total(accounts, line_type):
            total = TransactionLine.objects.filter(
                account__in=accounts,
                journal__is_posted=True,
                journal__date__gte=from_date,
                journal__date__lte=to_date,
                type=line_type,
            ).aggregate(t=Sum('amount'))['t'] or Decimal('0')

            opposite = TransactionLine.objects.filter(
                account__in=accounts,
                journal__is_posted=True,
                journal__date__gte=from_date,
                journal__date__lte=to_date,
            ).exclude(type=line_type).aggregate(t=Sum('amount'))['t'] or Decimal('0')
            return total - opposite

        total_income  = get_account_total(income_accounts, 'credit')
        total_expense = get_account_total(expense_accounts, 'debit')
        net           = total_income - total_expense

        # বিস্তারিত income lines
        income_details = []
        for acc in income_accounts:
            amt = TransactionLine.objects.filter(
                account=acc, journal__is_posted=True,
                journal__date__gte=from_date, journal__date__lte=to_date,
            ).aggregate(
                cr=Sum('amount', filter=Q(type='credit')),
                dr=Sum('amount', filter=Q(type='debit')),
            )
            val = (amt['cr'] or 0) - (amt['dr'] or 0)
            if val != 0:
                income_details.append({'account': acc.name, 'amount': float(val)})

        # বিস্তারিত expense lines
        expense_details = []
        for acc in expense_accounts:
            amt = TransactionLine.objects.filter(
                account=acc, journal__is_posted=True,
                journal__date__gte=from_date, journal__date__lte=to_date,
            ).aggregate(
                dr=Sum('amount', filter=Q(type='debit')),
                cr=Sum('amount', filter=Q(type='credit')),
            )
            val = (amt['dr'] or 0) - (amt['cr'] or 0)
            if val != 0:
                expense_details.append({'account': acc.name, 'amount': float(val)})

        return {
            'from_date':       str(from_date),
            'to_date':         str(to_date),
            'total_income':    float(total_income),
            'total_expense':   float(total_expense),
            'net_profit_loss': float(net),
            'is_profit':       net >= 0,
            'income_details':  income_details,
            'expense_details': expense_details,
        }

    @staticmethod
    def get_balance_sheet(as_of: date) -> dict:
        """
        Balance Sheet — Assets = Liabilities + Equity।
        একটি নির্দিষ্ট তারিখে কোম্পানির financial position।
        """
        def get_group_balance(type_name_contains: str) -> tuple:
            """একটি account type group-এর সব account-এর balance।"""
            accs = Account.objects.filter(
                account_type__name__icontains=type_name_contains,
                is_active=True,
                is_group=False,
            )
            items = []
            total = Decimal('0')
            for acc in accs:
                lines = TransactionLine.objects.filter(
                    account=acc,
                    journal__is_posted=True,
                    journal__date__lte=as_of,
                )
                dr = lines.filter(type='debit').aggregate(t=Sum('amount'))['t'] or Decimal('0')
                cr = lines.filter(type='credit').aggregate(t=Sum('amount'))['t'] or Decimal('0')
                if acc.account_type.nature == 'debit':
                    bal = acc.opening_balance + dr - cr
                else:
                    bal = acc.opening_balance + cr - dr
                if bal != 0:
                    items.append({'account': f"{acc.code} {acc.name}", 'balance': float(bal)})
                    total += bal
            return items, float(total)

        asset_items,     total_assets     = get_group_balance('asset')
        liability_items, total_liabilities = get_group_balance('liabilit')
        equity_items,    total_equity     = get_group_balance('equity')

        return {
            'as_of':             str(as_of),
            'assets':            {'items': asset_items,     'total': total_assets},
            'liabilities':       {'items': liability_items, 'total': total_liabilities},
            'equity':            {'items': equity_items,    'total': total_equity},
            'total_liab_equity': total_liabilities + total_equity,
            'is_balanced':       abs(total_assets - (total_liabilities + total_equity)) < 1,
        }

    @staticmethod
    def get_cash_book(from_date: date, to_date: date) -> dict:
        """
        Cash Book — Cash account-এর সব লেনদেনের তালিকা।
        Opening balance + Receipts - Payments = Closing balance।
        """
        try:
            cash_account = Account.objects.get(code=CASH_IN_HAND_CODE)
        except Account.DoesNotExist:
            return {'error': 'Cash account not configured'}

        # Opening balance (এই period-এর আগের সব transaction)
        prev_lines = TransactionLine.objects.filter(
            account=cash_account,
            journal__is_posted=True,
            journal__date__lt=from_date,
        )
        prev_dr = prev_lines.filter(type='debit').aggregate(t=Sum('amount'))['t'] or Decimal('0')
        prev_cr = prev_lines.filter(type='credit').aggregate(t=Sum('amount'))['t'] or Decimal('0')
        opening = cash_account.opening_balance + prev_dr - prev_cr

        # এই period-এর transactions
        period_lines = TransactionLine.objects.filter(
            account=cash_account,
            journal__is_posted=True,
            journal__date__gte=from_date,
            journal__date__lte=to_date,
        ).select_related('journal').order_by('journal__date', 'journal__created_at')

        entries = []
        running = opening
        total_receipts  = Decimal('0')
        total_payments  = Decimal('0')

        for line in period_lines:
            if line.type == 'debit':
                running += line.amount
                total_receipts += line.amount
                entries.append({
                    'date':        str(line.journal.date),
                    'entry_no':    line.journal.entry_no,
                    'description': line.journal.description[:80],
                    'receipt':     float(line.amount),
                    'payment':     None,
                    'balance':     float(running),
                })
            else:
                running -= line.amount
                total_payments += line.amount
                entries.append({
                    'date':        str(line.journal.date),
                    'entry_no':    line.journal.entry_no,
                    'description': line.journal.description[:80],
                    'receipt':     None,
                    'payment':     float(line.amount),
                    'balance':     float(running),
                })

        return {
            'from_date':      str(from_date),
            'to_date':        str(to_date),
            'opening_balance': float(opening),
            'closing_balance': float(running),
            'total_receipts':  float(total_receipts),
            'total_payments':  float(total_payments),
            'entries':         entries,
        }

    @staticmethod
    def compare_profit_loss(year1_from: date, year1_to: date,
                             year2_from: date, year2_to: date) -> dict:
        """দুটি period-এর P&L তুলনা করা।"""
        pl1 = ReportService.get_profit_loss(year1_from, year1_to)
        pl2 = ReportService.get_profit_loss(year2_from, year2_to)
        return {
            'period1': {**pl1, 'label': f"{year1_from} to {year1_to}"},
            'period2': {**pl2, 'label': f"{year2_from} to {year2_to}"},
            'income_change':  pl1['total_income']    - pl2['total_income'],
            'expense_change': pl1['total_expense']   - pl2['total_expense'],
            'profit_change':  pl1['net_profit_loss'] - pl2['net_profit_loss'],
        }


class DailyAccountService:
    """দৈনিক হিসাব বন্ধ করার service।"""

    @staticmethod
    @transaction.atomic
    def close_day(target_date: date, closed_by=None) -> 'DailyAccount':
        """
        একটি দিনের হিসাব বন্ধ করা।
        Income, Expense, Payment সব গণনা করে DailyAccount record তৈরি করে।
        """
        from apps.daily_account.models import DailyAccount
        from apps.income.models import Income
        from apps.expense.models import Expense
        from apps.billing.models import Payment
        from django.db.models import Sum

        # আগের দিনের closing = আজকের opening
        prev_day = DailyAccount.objects.filter(date__lt=target_date, status='closed').order_by('-date').first()
        opening_cash = prev_day.closing_cash if prev_day else Decimal('0')

        # আজকের income
        income_agg = Income.objects.filter(date=target_date).aggregate(
            total=Sum('amount'),
            cash=Sum('amount', filter=Q(method='cash')),
            bkash=Sum('amount', filter=Q(method='bkash')),
            nagad=Sum('amount', filter=Q(method='nagad')),
            rocket=Sum('amount', filter=Q(method='rocket')),
            bank=Sum('amount', filter=Q(method='bank')),
        )

        # Bill collection (Payment model থেকে)
        bill_collection = Payment.objects.filter(payment_date=target_date).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        # Payment method breakdown
        pay_agg = Payment.objects.filter(payment_date=target_date).aggregate(
            cash=Sum('amount', filter=Q(method='cash')),
            bkash=Sum('amount', filter=Q(method='bkash')),
            nagad=Sum('amount', filter=Q(method='nagad')),
            rocket=Sum('amount', filter=Q(method='rocket')),
            bank=Sum('amount', filter=Q(method='bank')),
        )

        total_income = (income_agg['total'] or Decimal('0')) + bill_collection

        # আজকের expense
        expense_total = Expense.objects.filter(date=target_date).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        closing_cash = opening_cash + total_income - expense_total
        net          = total_income - expense_total

        daily, _ = DailyAccount.objects.update_or_create(
            date=target_date,
            defaults={
                'total_income':     total_income,
                'bill_collection':  bill_collection,
                'connection_fee':   income_agg.get('total') or Decimal('0'),
                'other_income':     (income_agg['total'] or Decimal('0')),
                'total_expense':    expense_total,
                'opening_cash':     opening_cash,
                'closing_cash':     closing_cash,
                'net_profit_loss':  net,
                'cash_in_hand':     (pay_agg.get('cash') or Decimal('0')) + (income_agg.get('cash') or Decimal('0')),
                'bkash_total':      (pay_agg.get('bkash') or Decimal('0')) + (income_agg.get('bkash') or Decimal('0')),
                'nagad_total':      (pay_agg.get('nagad') or Decimal('0')) + (income_agg.get('nagad') or Decimal('0')),
                'bank_total':       (pay_agg.get('bank') or Decimal('0')) + (income_agg.get('bank') or Decimal('0')),
                'status':           DailyAccount.Status.CLOSED,
                'closed_by':        closed_by,
                'closed_at':        timezone.now(),
            }
        )

        logger.info(f"Day closed: {target_date} | Income={total_income} | Expense={expense_total} | Net={net}")
        return daily
