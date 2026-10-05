# ফাইল: backend/apps/billing/models.py
# ISP-BCRM সিস্টেমের Billing ও Payment model।
# প্রতি মাসে client-এর বিল generate হয় এবং payment track করা হয়।

from django.db import models
from django.core.validators import MinValueValidator
from apps.accounts.models import User


class Billing(models.Model):
    """
    প্রতি মাসের billing record।
    bill_month = যে মাসের বিল, amount = কত টাকা, paid = কত পরিশোধ হয়েছে।
    """

    class BillStatus(models.TextChoices):
        UNPAID  = 'unpaid',  'Unpaid'
        PARTIAL = 'partial', 'Partial'
        PAID    = 'paid',    'Paid'
        WAIVED  = 'waived',  'Waived/Forgiven'
        OVERDUE = 'overdue', 'Overdue'

    client       = models.ForeignKey(
        'clients.Client', on_delete=models.CASCADE, related_name='billings'
    )
    bill_month   = models.DateField(help_text='বিলের মাস (YYYY-MM-01 format)')
    bill_amount  = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    discount     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payable_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    paid_amount  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    due_amount   = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advance_used = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                       help_text='Advance balance থেকে কত কেটেছে')

    status       = models.CharField(max_length=10, choices=BillStatus.choices, default=BillStatus.UNPAID, db_index=True)
    bill_date    = models.DateField(help_text='যে তারিখে বিল generate হয়েছে')
    due_date     = models.DateField(help_text='পরিশোধের শেষ তারিখ (expiry_date)')

    note         = models.TextField(blank=True)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                      blank=True, related_name='bills_generated')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'billings'
        verbose_name = 'Billing'
        ordering     = ['-bill_month', '-created_at']
        unique_together = [('client', 'bill_month')]
        indexes = [
            models.Index(fields=['status', 'bill_month']),
            models.Index(fields=['client', 'bill_month']),
            models.Index(fields=['due_date', 'status']),
        ]

    def __str__(self):
        return f"{self.client.username} | {self.bill_month.strftime('%b %Y')} | {self.status}"

    @property
    def remaining_due(self):
        """এই বিলে এখনো কত টাকা বাকি।"""
        return max(0, self.payable_amount - self.paid_amount)


class Payment(models.Model):
    """
    Client-এর প্রতিটি payment entry।
    একটি billing-এ একাধিক partial payment থাকতে পারে।
    """

    class PaymentMethod(models.TextChoices):
        CASH    = 'cash',    'Cash'
        BKASH   = 'bkash',   'bKash'
        NAGAD   = 'nagad',   'Nagad'
        ROCKET  = 'rocket',  'Rocket'
        BANK    = 'bank',    'Bank Transfer'
        CARD    = 'card',    'Card'
        ONLINE  = 'online',  'Online (SSL Commerz)'
        ADVANCE = 'advance', 'From Advance Balance'
        WAIVER  = 'waiver',  'Waiver/Forgiven'

    client     = models.ForeignKey('clients.Client', on_delete=models.CASCADE, related_name='payments')
    billing    = models.ForeignKey(Billing, on_delete=models.CASCADE, related_name='payments',
                                   null=True, blank=True)
    amount     = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.01)])
    method     = models.CharField(max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.CASH)

    # Transaction reference (bKash / Nagad / Bank trx ID)
    transaction_id = models.CharField(max_length=100, blank=True, db_index=True)

    # কে collect করেছে
    collected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='payments_collected')

    note       = models.TextField(blank=True)
    payment_date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'payments'
        verbose_name = 'Payment'
        ordering     = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'payment_date']),
            models.Index(fields=['method', 'payment_date']),
        ]

    def __str__(self):
        return f"{self.client.username} | {self.amount} BDT | {self.method} | {self.payment_date}"
