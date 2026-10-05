# ফাইল: backend/apps/hr/models.py
# ISP-BCRM HR & Payroll module-এর সব model এখানে।
# Department, Position, Employee, Payhead, Payroll, Payslip, Attendance,
# ResignRule, Resignation, Rejoin — সব এখানে সংজ্ঞায়িত।

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.accounts.models import User


# =============================================================
# Department & Position
# =============================================================

class Department(models.Model):
    """বিভাগ — যেমন: Technical, Sales, Accounts, Management।"""
    name        = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'hr_departments'
        verbose_name = 'Department'
        ordering     = ['name']

    def __str__(self):
        return self.name


class Position(models.Model):
    """পদবি / পদ — যেমন: Network Engineer, Field Technician, Manager।"""
    name        = models.CharField(max_length=100)
    department  = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True,
                                     related_name='positions')
    description = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'hr_positions'
        verbose_name = 'Position'
        ordering     = ['department', 'name']

    def __str__(self):
        return f"{self.name} ({self.department})"


# =============================================================
# Employee
# =============================================================

class Employee(models.Model):
    """
    কর্মচারীর সম্পূর্ণ তথ্য।
    User account-এর সাথে one-to-one সম্পর্ক।
    """

    class EmploymentType(models.TextChoices):
        FULL_TIME  = 'full_time',  'Full Time'
        PART_TIME  = 'part_time',  'Part Time'
        CONTRACT   = 'contract',   'Contract'
        INTERN     = 'intern',     'Intern'

    class Status(models.TextChoices):
        ACTIVE     = 'active',     'Active'
        INACTIVE   = 'inactive',   'Inactive'
        RESIGNED   = 'resigned',   'Resigned'
        TERMINATED = 'terminated', 'Terminated'
        ON_LEAVE   = 'on_leave',   'On Leave'

    class BloodGroup(models.TextChoices):
        A_POS  = 'A+',  'A+'
        A_NEG  = 'A-',  'A-'
        B_POS  = 'B+',  'B+'
        B_NEG  = 'B-',  'B-'
        O_POS  = 'O+',  'O+'
        O_NEG  = 'O-',  'O-'
        AB_POS = 'AB+', 'AB+'
        AB_NEG = 'AB-', 'AB-'

    # User Account সংযোগ
    user            = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name='employee_profile')

    # Employee ID (auto-generate করা হয়)
    employee_id     = models.CharField(max_length=20, unique=True, verbose_name='Employee ID')

    # ব্যক্তিগত তথ্য
    full_name       = models.CharField(max_length=150)
    father_name     = models.CharField(max_length=150, blank=True)
    mother_name     = models.CharField(max_length=150, blank=True)
    date_of_birth   = models.DateField(null=True, blank=True)
    gender          = models.CharField(max_length=10, choices=[('male','Male'),('female','Female'),('other','Other')], blank=True)
    blood_group     = models.CharField(max_length=5, choices=BloodGroup.choices, blank=True)
    nid             = models.CharField(max_length=20, blank=True, verbose_name='NID Number')
    phone           = models.CharField(max_length=20)
    alt_phone       = models.CharField(max_length=20, blank=True)
    email           = models.EmailField(blank=True)

    # ঠিকানা
    present_address = models.TextField(blank=True, verbose_name='Present Address')
    permanent_address = models.TextField(blank=True, verbose_name='Permanent Address')

    # পদ ও বিভাগ
    department      = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True,
                                        related_name='employees')
    position        = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True,
                                        related_name='employees')
    employment_type = models.CharField(max_length=15, choices=EmploymentType.choices,
                                       default=EmploymentType.FULL_TIME)
    reporting_to    = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='subordinates', verbose_name='Reports To')

    # চাকরির তথ্য
    joining_date    = models.DateField()
    confirmation_date = models.DateField(null=True, blank=True)
    contract_end_date = models.DateField(null=True, blank=True)
    status          = models.CharField(max_length=15, choices=Status.choices,
                                       default=Status.ACTIVE, db_index=True)

    # বেতন তথ্য
    basic_salary    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    bank_name       = models.CharField(max_length=100, blank=True)
    bank_account_no = models.CharField(max_length=50, blank=True)
    bkash_number    = models.CharField(max_length=20, blank=True)

    # শিক্ষা তথ্য
    education       = models.TextField(blank=True)

    # ছবি ও ডকুমেন্ট
    photo           = models.ImageField(upload_to='employees/photos/', blank=True, null=True)
    nid_photo       = models.ImageField(upload_to='employees/nid/', blank=True, null=True)
    documents       = models.FileField(upload_to='employees/docs/', blank=True, null=True)

    notes           = models.TextField(blank=True)
    created_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                        related_name='employees_created')
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'hr_employees'
        verbose_name = 'Employee'
        ordering     = ['full_name']
        indexes      = [
            models.Index(fields=['department', 'status']),
            models.Index(fields=['status', 'joining_date']),
        ]

    def __str__(self):
        return f"{self.employee_id} | {self.full_name}"

    def save(self, *args, **kwargs):
        # Employee ID auto-generate করা (EMP-001, EMP-002 ...)
        if not self.employee_id:
            last = Employee.objects.order_by('-id').first()
            next_num = (last.id + 1) if last else 1
            self.employee_id = f"EMP-{next_num:04d}"
        super().save(*args, **kwargs)

    @property
    def years_of_service(self):
        """চাকরির বয়স বছরে।"""
        if self.joining_date:
            delta = timezone.now().date() - self.joining_date
            return round(delta.days / 365, 1)
        return 0


# =============================================================
# Payhead (বেতনের উপাদান)
# =============================================================

class Payhead(models.Model):
    """
    বেতনের component — যেমন: Basic Salary, House Rent, Medical, TA/DA, Overtime, Deduction।
    প্রতিটি payhead earning বা deduction হতে পারে।
    """

    class HeadType(models.TextChoices):
        EARNING   = 'earning',   'Earning (যোগ হবে)'
        DEDUCTION = 'deduction', 'Deduction (বাদ যাবে)'

    class CalcMethod(models.TextChoices):
        FIXED      = 'fixed',      'Fixed Amount'
        PERCENTAGE = 'percentage', '% of Basic Salary'

    name        = models.CharField(max_length=100, unique=True, verbose_name='Payhead Name')
    head_type   = models.CharField(max_length=12, choices=HeadType.choices, default=HeadType.EARNING)
    calc_method = models.CharField(max_length=12, choices=CalcMethod.choices, default=CalcMethod.FIXED)
    default_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                          help_text='Fixed amount বা percentage value')
    is_taxable  = models.BooleanField(default=False)
    is_active   = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    sort_order  = models.PositiveSmallIntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'hr_payheads'
        verbose_name = 'Payhead'
        ordering     = ['sort_order', 'name']

    def __str__(self):
        return f"{self.name} ({self.head_type})"


# =============================================================
# Payroll (মাসিক বেতন তৈরি)
# =============================================================

class Payroll(models.Model):
    """
    মাসিক payroll record।
    প্রতি মাসে একটি payroll তৈরি হয় যার মধ্যে সব কর্মচারীর payslip থাকে।
    """

    class PayrollStatus(models.TextChoices):
        DRAFT     = 'draft',     'Draft'
        APPROVED  = 'approved',  'Approved'
        DISBURSED = 'disbursed', 'Disbursed/Paid'

    month       = models.DateField(help_text='বেতনের মাস (YYYY-MM-01 format)')
    title       = models.CharField(max_length=150, blank=True)
    status      = models.CharField(max_length=12, choices=PayrollStatus.choices,
                                   default=PayrollStatus.DRAFT)
    note        = models.TextField(blank=True)
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                     related_name='payrolls_created')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='payrolls_approved')
    approved_at = models.DateTimeField(null=True, blank=True)
    disbursed_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'hr_payrolls'
        verbose_name    = 'Payroll'
        ordering        = ['-month']
        unique_together = [('month',)]

    def __str__(self):
        return f"Payroll {self.month.strftime('%b %Y')} [{self.status}]"

    @property
    def total_gross(self):
        return self.payslips.aggregate(t=models.Sum('gross_salary'))['t'] or 0

    @property
    def total_net(self):
        return self.payslips.aggregate(t=models.Sum('net_salary'))['t'] or 0

    @property
    def employee_count(self):
        return self.payslips.count()


class Payslip(models.Model):
    """
    প্রতিটি কর্মচারীর মাসিক payslip।
    Payroll-এর একটি line-item।
    """

    payroll     = models.ForeignKey(Payroll, on_delete=models.CASCADE, related_name='payslips')
    employee    = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payslips')

    # বেতনের ভাঙ্গন
    basic_salary     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_earning    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_deduction  = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gross_salary     = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_salary       = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # উপস্থিতি তথ্য (এই মাসের)
    working_days     = models.PositiveSmallIntegerField(default=0)
    present_days     = models.PositiveSmallIntegerField(default=0)
    absent_days      = models.PositiveSmallIntegerField(default=0)
    leave_days       = models.PositiveSmallIntegerField(default=0)
    overtime_hours   = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # বোনাস / অতিরিক্ত adjustment
    bonus            = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    advance_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                              verbose_name='Advance Salary Deduction')
    loan_deduction   = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    is_paid          = models.BooleanField(default=False)
    paid_at          = models.DateTimeField(null=True, blank=True)
    note             = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'hr_payslips'
        verbose_name    = 'Payslip'
        ordering        = ['payroll', 'employee__full_name']
        unique_together = [('payroll', 'employee')]

    def __str__(self):
        return f"{self.employee} | {self.payroll.month.strftime('%b %Y')} | {self.net_salary}"


class PayslipItem(models.Model):
    """
    Payslip-এর প্রতিটি payhead item।
    Payslip → PayslipItem হল master-detail সম্পর্ক।
    """
    payslip    = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name='items')
    payhead    = models.ForeignKey(Payhead, on_delete=models.CASCADE)
    amount     = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'hr_payslip_items'

    def __str__(self):
        return f"{self.payhead.name}: {self.amount}"


# =============================================================
# Attendance (উপস্থিতি)
# =============================================================

class Attendance(models.Model):
    """
    কর্মচারীর দৈনিক উপস্থিতি record।
    Check-in, check-out, overtime সব এখানে।
    """

    class AttendanceStatus(models.TextChoices):
        PRESENT  = 'present',  'Present'
        ABSENT   = 'absent',   'Absent'
        LATE     = 'late',     'Late'
        HALF_DAY = 'half_day', 'Half Day'
        HOLIDAY  = 'holiday',  'Holiday'
        WEEKEND  = 'weekend',  'Weekend'
        ON_LEAVE = 'on_leave', 'On Leave'

    employee    = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendances')
    date        = models.DateField()
    status      = models.CharField(max_length=10, choices=AttendanceStatus.choices,
                                   default=AttendanceStatus.PRESENT)
    check_in    = models.TimeField(null=True, blank=True)
    check_out   = models.TimeField(null=True, blank=True)
    overtime_hours = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    note        = models.TextField(blank=True)
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'hr_attendance'
        verbose_name    = 'Attendance'
        ordering        = ['-date', 'employee__full_name']
        unique_together = [('employee', 'date')]
        indexes         = [models.Index(fields=['employee', 'date'])]

    def __str__(self):
        return f"{self.employee} | {self.date} | {self.status}"

    @property
    def working_hours(self):
        """মোট কাজের ঘণ্টা।"""
        if self.check_in and self.check_out:
            from datetime import datetime, date as date_cls
            ci = datetime.combine(date_cls.today(), self.check_in)
            co = datetime.combine(date_cls.today(), self.check_out)
            delta = co - ci
            return round(delta.seconds / 3600, 2)
        return 0


# =============================================================
# Resign Rules, Resignation & Rejoin
# =============================================================

class ResignRule(models.Model):
    """
    পদত্যাগের নিয়মাবলী।
    Notice period, settlement calculation rules ইত্যাদি।
    """
    name            = models.CharField(max_length=150, unique=True)
    notice_days     = models.PositiveSmallIntegerField(default=30,
                         help_text='Notice period (দিনে)')
    gratuity_applicable = models.BooleanField(default=True,
                             help_text='Gratuity প্রযোজ্য কিনা')
    gratuity_years_required = models.PositiveSmallIntegerField(default=3,
                                  help_text='Gratuity-র জন্য ন্যূনতম বছর')
    leave_encashment = models.BooleanField(default=True,
                          help_text='Unused leave encash করা যাবে কিনা')
    description     = models.TextField(blank=True)
    is_active       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'hr_resign_rules'
        verbose_name = 'Resign Rule'

    def __str__(self):
        return self.name


class Resignation(models.Model):
    """
    কর্মচারীর পদত্যাগ / বরখাস্তের রেকর্ড।
    """

    class ResignType(models.TextChoices):
        VOLUNTARY   = 'voluntary',   'Voluntary Resignation'
        TERMINATION = 'termination', 'Termination by Company'
        CONTRACT_END = 'contract_end', 'Contract Ended'
        RETIREMENT  = 'retirement',  'Retirement'

    class Status(models.TextChoices):
        PENDING   = 'pending',   'Pending Approval'
        APPROVED  = 'approved',  'Approved'
        REJECTED  = 'rejected',  'Rejected'
        COMPLETED = 'completed', 'Completed'

    employee        = models.ForeignKey(Employee, on_delete=models.CASCADE,
                                        related_name='resignations')
    resign_type     = models.CharField(max_length=15, choices=ResignType.choices,
                                       default=ResignType.VOLUNTARY)
    resign_rule     = models.ForeignKey(ResignRule, on_delete=models.SET_NULL, null=True)
    apply_date      = models.DateField(default=timezone.now)
    last_working_date = models.DateField()
    reason          = models.TextField()
    status          = models.CharField(max_length=12, choices=Status.choices,
                                       default=Status.PENDING)

    # Settlement
    gratuity_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    leave_encash    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_settlement = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    approved_by     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='resignations_approved')
    approved_at     = models.DateTimeField(null=True, blank=True)
    note            = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'hr_resignations'
        verbose_name = 'Resignation'
        ordering     = ['-apply_date']

    def __str__(self):
        return f"{self.employee} | {self.resign_type} | {self.apply_date}"


class Rejoin(models.Model):
    """
    পূর্বে পদত্যাগ করা কর্মচারীর পুনরায় যোগদানের রেকর্ড।
    """
    employee        = models.ForeignKey(Employee, on_delete=models.CASCADE,
                                        related_name='rejoins')
    previous_resignation = models.ForeignKey(Resignation, on_delete=models.SET_NULL,
                                              null=True, blank=True)
    rejoin_date     = models.DateField()
    department      = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    position        = models.ForeignKey(Position, on_delete=models.SET_NULL, null=True)
    new_basic_salary = models.DecimalField(max_digits=10, decimal_places=2)
    reason          = models.TextField(blank=True)
    approved_by     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                        related_name='rejoins_approved')
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'hr_rejoins'
        verbose_name = 'Rejoin'
        ordering     = ['-rejoin_date']

    def __str__(self):
        return f"{self.employee} rejoined {self.rejoin_date}"
