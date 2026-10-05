# ফাইল: backend/apps/leave/models.py
# Leave Management module — Category, Setup, Apply, Approval।

from django.db import models
from django.utils import timezone
from apps.accounts.models import User
from apps.hr.models import Employee


class LeaveCategory(models.Model):
    """
    ছুটির ধরন — যেমন: Annual Leave, Sick Leave, Casual Leave, Maternity Leave।
    """
    name            = models.CharField(max_length=100, unique=True)
    short_code      = models.CharField(max_length=5, unique=True, help_text='যেমন: AL, SL, CL')
    description     = models.TextField(blank=True)
    color           = models.CharField(max_length=10, default='#3B82F6', help_text='Calendar-এ color')
    is_paid         = models.BooleanField(default=True, help_text='Paid ছুটি কিনা')
    is_active       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'leave_categories'
        verbose_name = 'Leave Category'
        ordering     = ['name']

    def __str__(self):
        return f"{self.name} ({self.short_code})"


class LeaveSetup(models.Model):
    """
    Leave allocation setup — কোন ধরনের ছুটি প্রতি বছর কতদিন পাওয়া যাবে।
    Employment type অনুযায়ী আলাদা setup থাকতে পারে।
    """
    category        = models.ForeignKey(LeaveCategory, on_delete=models.CASCADE,
                                         related_name='setups')
    employment_type = models.CharField(
        max_length=15,
        choices=[('full_time','Full Time'),('part_time','Part Time'),
                 ('contract','Contract'),('intern','Intern'),('all','All')],
        default='all',
    )
    days_per_year   = models.PositiveSmallIntegerField(default=0,
                          help_text='প্রতি বছর কতদিন ছুটি পাবে')
    carry_forward   = models.BooleanField(default=False,
                          help_text='পরের বছরে carry forward করা যাবে কিনা')
    max_carry_days  = models.PositiveSmallIntegerField(default=0,
                          help_text='সর্বোচ্চ কতদিন carry forward করা যাবে')
    encashable      = models.BooleanField(default=False,
                          help_text='Unused leave encash করা যাবে কিনা')
    min_service_days = models.PositiveSmallIntegerField(default=0,
                           help_text='Apply করতে ন্যূনতম কতদিন চাকরি করতে হবে')
    is_active       = models.BooleanField(default=True)
    fiscal_year     = models.CharField(max_length=9, default='2026-2027',
                          help_text='অর্থবছর — যেমন: 2026-2027')
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'leave_setups'
        verbose_name    = 'Leave Setup'
        unique_together = [('category', 'employment_type', 'fiscal_year')]

    def __str__(self):
        return f"{self.category} | {self.employment_type} | {self.days_per_year}d/yr"


class LeaveBalance(models.Model):
    """
    প্রতিটি কর্মচারীর leave balance।
    বছরের শুরুতে allocate হয়, apply করলে কমে।
    """
    employee        = models.ForeignKey(Employee, on_delete=models.CASCADE,
                                         related_name='leave_balances')
    category        = models.ForeignKey(LeaveCategory, on_delete=models.CASCADE)
    fiscal_year     = models.CharField(max_length=9, default='2026-2027')
    total_days      = models.PositiveSmallIntegerField(default=0,
                          help_text='মোট বরাদ্দ ছুটি')
    used_days       = models.PositiveSmallIntegerField(default=0,
                          help_text='ব্যবহৃত ছুটি')
    carry_forward_days = models.PositiveSmallIntegerField(default=0)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'leave_balances'
        verbose_name    = 'Leave Balance'
        unique_together = [('employee', 'category', 'fiscal_year')]

    def __str__(self):
        return f"{self.employee} | {self.category} | {self.remaining}d remaining"

    @property
    def remaining(self):
        return max(0, self.total_days + self.carry_forward_days - self.used_days)


class LeaveApplication(models.Model):
    """
    ছুটির আবেদন।
    কর্মচারী apply করে, supervisor approve বা reject করে।
    """

    class Status(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        APPROVED  = 'approved',  'Approved'
        REJECTED  = 'rejected',  'Rejected'
        CANCELLED = 'cancelled', 'Cancelled'

    employee        = models.ForeignKey(Employee, on_delete=models.CASCADE,
                                         related_name='leave_applications')
    category        = models.ForeignKey(LeaveCategory, on_delete=models.CASCADE)
    start_date      = models.DateField()
    end_date        = models.DateField()
    total_days      = models.PositiveSmallIntegerField(default=1)
    reason          = models.TextField()
    status          = models.CharField(max_length=12, choices=Status.choices,
                                       default=Status.PENDING, db_index=True)

    # Approval
    reviewed_by     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='leaves_reviewed')
    reviewed_at     = models.DateTimeField(null=True, blank=True)
    review_note     = models.TextField(blank=True)

    # Supporting document
    attachment      = models.FileField(upload_to='leave/attachments/', blank=True, null=True)

    applied_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'leave_applications'
        verbose_name = 'Leave Application'
        ordering     = ['-applied_at']
        indexes      = [
            models.Index(fields=['employee', 'status']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        return f"{self.employee} | {self.category} | {self.start_date} → {self.end_date} [{self.status}]"

    def save(self, *args, **kwargs):
        # total_days auto-calculate করা
        if self.start_date and self.end_date:
            delta = self.end_date - self.start_date
            self.total_days = delta.days + 1
        super().save(*args, **kwargs)
