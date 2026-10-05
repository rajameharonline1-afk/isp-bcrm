# ফাইল: backend/apps/expense/models.py
# Expense module — Expense Category, Daily Expense, Expense History।

from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from apps.accounts.models import User


class ExpenseCategory(models.Model):
    """ব্যয়ের ধরন — যেমন: Office Rent, Salary, Equipment, Bandwidth Cost, Misc।"""
    name         = models.CharField(max_length=100, unique=True)
    description  = models.TextField(blank=True)
    account_code = models.CharField(max_length=20, blank=True,
                                     help_text='Chart of Accounts-এর account code')
    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'expense_categories'
        verbose_name = 'Expense Category'
        ordering     = ['name']

    def __str__(self):
        return self.name


class Expense(models.Model):
    """
    দৈনিক ব্যয়ের রেকর্ড।
    Office খরচ, equipment, bandwidth cost ইত্যাদি।
    """
    class PaymentMethod(models.TextChoices):
        CASH   = 'cash',   'Cash'
        BKASH  = 'bkash',  'bKash'
        NAGAD  = 'nagad',  'Nagad'
        ROCKET = 'rocket', 'Rocket'
        BANK   = 'bank',   'Bank Transfer'
        OTHER  = 'other',  'Other'

    category        = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT,
                                         related_name='expenses')
    amount          = models.DecimalField(max_digits=12, decimal_places=2,
                                           validators=[MinValueValidator(0.01)])
    date            = models.DateField(default=timezone.now, db_index=True)
    method          = models.CharField(max_length=10, choices=PaymentMethod.choices,
                                        default=PaymentMethod.CASH)
    reference_no    = models.CharField(max_length=100, blank=True)
    description     = models.TextField(blank=True)

    # Vendor/Payee
    payee           = models.CharField(max_length=150, blank=True, verbose_name='Paid To (Payee)')
    attachment      = models.FileField(upload_to='expense/attachments/', blank=True, null=True)

    # Accounting journal entry link
    journal_entry   = models.ForeignKey('accounting.JournalEntry', on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name='+')

    approved_by     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='expenses_approved')
    recorded_by     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                         related_name='expenses_recorded')
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'expenses'
        verbose_name = 'Expense'
        ordering     = ['-date', '-created_at']
        indexes      = [
            models.Index(fields=['date', 'category']),
            models.Index(fields=['method', 'date']),
        ]

    def __str__(self):
        return f"{self.category} | {self.amount} | {self.date}"
