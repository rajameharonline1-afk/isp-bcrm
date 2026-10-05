# ফাইল: backend/apps/accounting/models.py
# ISP-BCRM Accounting module — Double-entry bookkeeping system।
# Chart of Accounts, Journal Entry, Transaction, Account Balance সব এখানে।

from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from apps.accounts.models import User


# =============================================================
# Chart of Accounts (হিসাবের তালিকা)
# =============================================================

class AccountType(models.Model):
    """
    Account-এর ধরন — Asset, Liability, Equity, Income, Expense।
    Double-entry bookkeeping-এর মূল বিভাগ।
    """
    class NatureChoices(models.TextChoices):
        DEBIT  = 'debit',  'Debit (বামদিকে বাড়ে)'
        CREDIT = 'credit', 'Credit (ডানদিকে বাড়ে)'

    name        = models.CharField(max_length=50, unique=True)
    nature      = models.CharField(max_length=6, choices=NatureChoices.choices,
                                   help_text='Debit nature = Asset/Expense; Credit = Liability/Equity/Income')
    description = models.TextField(blank=True)
    sort_order  = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table     = 'acc_account_types'
        verbose_name = 'Account Type'
        ordering     = ['sort_order', 'name']

    def __str__(self):
        return self.name


class Account(models.Model):
    """
    Chart of Accounts — প্রতিটি individual account এখানে।
    Parent-child hierarchy দিয়ে group account সমর্থন করে।
    উদাহরণ: Assets > Current Assets > Cash in Hand
    """
    account_type    = models.ForeignKey(AccountType, on_delete=models.PROTECT, related_name='accounts')
    parent          = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='children', verbose_name='Parent Account')
    code            = models.CharField(max_length=20, unique=True, verbose_name='Account Code',
                                        help_text='যেমন: 1001, 2001, 4001')
    name            = models.CharField(max_length=150, verbose_name='Account Name')
    description     = models.TextField(blank=True)
    is_group        = models.BooleanField(default=False, verbose_name='Group Account?',
                                           help_text='Group account-এ সরাসরি transaction হয় না')
    is_system       = models.BooleanField(default=False, verbose_name='System Account?',
                                           help_text='System account delete করা যাবে না')
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                           verbose_name='Opening Balance (BDT)')
    is_active       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'acc_accounts'
        verbose_name = 'Account'
        ordering     = ['code']
        indexes      = [models.Index(fields=['account_type', 'is_active'])]

    def __str__(self):
        return f"{self.code} — {self.name}"

    @property
    def balance(self):
        """Account-এর current balance (opening + all transactions)।"""
        from django.db.models import Sum
        debit  = self.transaction_lines.filter(type='debit').aggregate(t=Sum('amount'))['t'] or 0
        credit = self.transaction_lines.filter(type='credit').aggregate(t=Sum('amount'))['t'] or 0
        if self.account_type.nature == 'debit':
            return self.opening_balance + debit - credit
        else:
            return self.opening_balance + credit - debit


# =============================================================
# Journal Entry & Transaction Lines
# =============================================================

class JournalEntry(models.Model):
    """
    Journal Entry — double-entry bookkeeping-এর মূল record।
    প্রতিটি entry-তে ন্যূনতম দুটি line থাকে: debit ও credit।
    Total debit = Total credit (balanced হতে হবে)।
    """
    class EntryType(models.TextChoices):
        MANUAL      = 'manual',      'Manual Journal'
        INCOME      = 'income',      'Income'
        EXPENSE     = 'expense',     'Expense'
        PAYMENT     = 'payment',     'Payment Collection'
        PURCHASE    = 'purchase',    'Purchase'
        SALARY      = 'salary',      'Salary Payment'
        TRANSFER    = 'transfer',    'Bank Transfer'
        OPENING     = 'opening',     'Opening Entry'
        ADJUSTMENT  = 'adjustment',  'Adjustment'

    entry_no    = models.CharField(max_length=30, unique=True, verbose_name='Journal Entry No.')
    date        = models.DateField(default=timezone.now, db_index=True)
    entry_type  = models.CharField(max_length=12, choices=EntryType.choices,
                                   default=EntryType.MANUAL)
    description = models.TextField(verbose_name='Narration / Description')

    # Reference to source document
    reference   = models.CharField(max_length=100, blank=True, verbose_name='Reference No.')
    reference_model = models.CharField(max_length=50, blank=True,
                                        help_text='যেমন: billing, payment, payslip')
    reference_id = models.PositiveIntegerField(null=True, blank=True)

    is_posted   = models.BooleanField(default=False, verbose_name='Posted?',
                                       help_text='Posted হলে edit/delete করা যাবে না')
    posted_by   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='journals_posted')
    posted_at   = models.DateTimeField(null=True, blank=True)
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                     related_name='journals_created')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'acc_journal_entries'
        verbose_name = 'Journal Entry'
        ordering     = ['-date', '-created_at']
        indexes      = [
            models.Index(fields=['date', 'entry_type']),
            models.Index(fields=['is_posted', 'date']),
        ]

    def __str__(self):
        return f"{self.entry_no} | {self.date} | {self.description[:50]}"

    def save(self, *args, **kwargs):
        if not self.entry_no:
            self.entry_no = JournalEntry._generate_entry_no()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_entry_no():
        from datetime import date
        today  = date.today()
        prefix = f"JV-{today.strftime('%Y%m')}-"
        last   = JournalEntry.objects.filter(entry_no__startswith=prefix).order_by('-entry_no').first()
        if last:
            try:
                seq = int(last.entry_no.split('-')[-1]) + 1
            except ValueError:
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:04d}"

    @property
    def total_debit(self):
        return self.lines.filter(type='debit').aggregate(
            t=models.Sum('amount'))['t'] or 0

    @property
    def total_credit(self):
        return self.lines.filter(type='credit').aggregate(
            t=models.Sum('amount'))['t'] or 0

    @property
    def is_balanced(self):
        """Debit = Credit হলে balanced।"""
        return abs(self.total_debit - self.total_credit) < 0.01


class TransactionLine(models.Model):
    """
    Journal Entry-র প্রতিটি line।
    Debit বা Credit — account ও amount।
    """
    class LineType(models.TextChoices):
        DEBIT  = 'debit',  'Debit (ডেবিট)'
        CREDIT = 'credit', 'Credit (ক্রেডিট)'

    journal     = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')
    account     = models.ForeignKey(Account, on_delete=models.PROTECT,
                                     related_name='transaction_lines')
    type        = models.CharField(max_length=6, choices=LineType.choices)
    amount      = models.DecimalField(max_digits=14, decimal_places=2,
                                       validators=[MinValueValidator(0.01)])
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table     = 'acc_transaction_lines'
        verbose_name = 'Transaction Line'

    def __str__(self):
        return f"{self.journal.entry_no} | {self.account.name} | {self.type} | {self.amount}"


# =============================================================
# Account Balance Snapshot (মাসিক balance cache)
# =============================================================

class AccountBalance(models.Model):
    """
    মাসিক account balance snapshot।
    Reports দ্রুত তৈরির জন্য pre-calculated balance।
    """
    account       = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='monthly_balances')
    period_month  = models.DateField(help_text='মাসের শুরুর তারিখ (YYYY-MM-01)')
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_debit   = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_credit  = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    closing_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'acc_account_balances'
        verbose_name    = 'Account Balance'
        unique_together = [('account', 'period_month')]
        ordering        = ['-period_month', 'account__code']

    def __str__(self):
        return f"{self.account} | {self.period_month} | {self.closing_balance}"
