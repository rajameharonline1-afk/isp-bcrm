# ফাইল: backend/apps/daily_account/models.py
# Daily Account — দৈনিক হিসাব বন্ধ করার record।
# প্রতিদিন শেষে total income, total expense, closing balance সংরক্ষণ করা হয়।

from django.db import models
from django.utils import timezone
from apps.accounts.models import User


class DailyAccount(models.Model):
    """
    দৈনিক হিসাব সমাপ্তির (Day Closing) record।
    প্রতিদিন একটি মাত্র record। Opening + Income - Expense = Closing।
    """
    class Status(models.TextChoices):
        OPEN   = 'open',   'Open'
        CLOSED = 'closed', 'Closed'

    date            = models.DateField(unique=True, default=timezone.now)

    # Income breakdown
    total_income         = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                               verbose_name='Total Income (BDT)')
    bill_collection      = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                               verbose_name='Bill Collection (BDT)')
    connection_fee       = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                               verbose_name='Connection Fee (BDT)')
    other_income         = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                               verbose_name='Other Income (BDT)')

    # Expense breakdown
    total_expense        = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                               verbose_name='Total Expense (BDT)')

    # Balance
    opening_cash         = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                               verbose_name='Opening Cash Balance (BDT)')
    closing_cash         = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                               verbose_name='Closing Cash Balance (BDT)')
    net_profit_loss      = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                               verbose_name='Net Profit / Loss (BDT)')

    # Cash breakdown by method
    cash_in_hand         = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bkash_total          = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    nagad_total          = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    rocket_total         = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    bank_total           = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status          = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    note            = models.TextField(blank=True)
    closed_by       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='daily_accounts_closed')
    closed_at       = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'daily_accounts'
        verbose_name = 'Daily Account'
        ordering     = ['-date']

    def __str__(self):
        return f"Daily Account | {self.date} | {self.status} | Net: {self.net_profit_loss}"
