# ফাইল: backend/apps/income/models.py
# Income module — Income Category, Daily Income, Income History।

from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from apps.accounts.models import User


class IncomeCategory(models.Model):
    """আয়ের ধরন — যেমন: Internet Bill, Connection Fee, OLT Service, Misc।"""
    name            = models.CharField(max_length=100, unique=True)
    description     = models.TextField(blank=True)
    # Accounting-এ কোন account-এ post হবে
    account_code    = models.CharField(max_length=20, blank=True,
                                        help_text='Chart of Accounts-এর account code')
    is_active       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'income_categories'
        verbose_name = 'Income Category'
        ordering     = ['name']

    def __str__(self):
        return self.name


class Income(models.Model):
    """
    দৈনিক আয়ের রেকর্ড।
    Billing payment ছাড়াও অন্যান্য আয় (connection fee, misc) এখানে।
    """
    class PaymentMethod(models.TextChoices):
        CASH   = 'cash',   'Cash'
        BKASH  = 'bkash',  'bKash'
        NAGAD  = 'nagad',  'Nagad'
        ROCKET = 'rocket', 'Rocket'
        BANK   = 'bank',   'Bank Transfer'
        OTHER  = 'other',  'Other'

    category        = models.ForeignKey(IncomeCategory, on_delete=models.PROTECT,
                                         related_name='incomes')
    amount          = models.DecimalField(max_digits=12, decimal_places=2,
                                           validators=[MinValueValidator(0.01)])
    date            = models.DateField(default=timezone.now, db_index=True)
    method          = models.CharField(max_length=10, choices=PaymentMethod.choices,
                                        default=PaymentMethod.CASH)
    reference_no    = models.CharField(max_length=100, blank=True)
    description     = models.TextField(blank=True)

    # Optional link to client/billing
    client          = models.ForeignKey('clients.Client', on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name='income_entries')
    billing         = models.ForeignKey('billing.Billing', on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name='+')

    # Accounting journal entry link
    journal_entry   = models.ForeignKey('accounting.JournalEntry', on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name='+')

    collected_by    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                         related_name='incomes_collected')
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'incomes'
        verbose_name = 'Income'
        ordering     = ['-date', '-created_at']
        indexes      = [
            models.Index(fields=['date', 'category']),
            models.Index(fields=['method', 'date']),
        ]

    def __str__(self):
        return f"{self.category} | {self.amount} | {self.date}"
