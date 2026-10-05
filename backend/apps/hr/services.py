# ফাইল: backend/apps/hr/services.py
# HR & Payroll-এর সব business logic এখানে।
# Payroll generate, payslip calculate, salary disburse, attendance summary।

import logging
from decimal import Decimal
from datetime import date
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class PayrollService:
    """
    Payroll তৈরি ও পরিচালনার সব logic এখানে।
    প্রতি মাসে সব কর্মচারীর payslip auto-generate করে।
    """

    @staticmethod
    @transaction.atomic
    def generate_payroll(month: date, created_by=None) -> tuple:
        """
        নির্দিষ্ট মাসের জন্য payroll তৈরি করা।
        সব active employee-র payslip generate করা হয়।
        Return: (payroll, created, skipped_employees)
        """
        from apps.hr.models import Payroll, Payslip, Employee

        month_start = month.replace(day=1)

        # ইতিমধ্যে এই মাসের payroll আছে কিনা
        payroll, created = Payroll.objects.get_or_create(
            month=month_start,
            defaults={
                'title': f"Salary - {month_start.strftime('%B %Y')}",
                'created_by': created_by,
            }
        )

        if payroll.status == Payroll.PayrollStatus.DISBURSED:
            return payroll, False, []

        # সব active employee-র payslip তৈরি করা
        employees = Employee.objects.filter(
            status=Employee.Status.ACTIVE,
            joining_date__lte=month_start + relativedelta(months=1),
        ).select_related('department', 'position')

        skipped = []
        generated = 0

        for emp in employees:
            try:
                PayrollService._generate_payslip(payroll, emp, month_start)
                generated += 1
            except Exception as exc:
                skipped.append({'employee': str(emp), 'error': str(exc)})
                logger.error(f"Payslip generation failed for {emp}: {exc}")

        logger.info(f"Payroll generated: {payroll} | {generated} payslips | {len(skipped)} skipped")
        return payroll, created, skipped

    @staticmethod
    def _generate_payslip(payroll, employee, month_start: date):
        """একটি কর্মচারীর payslip generate করা।"""
        from apps.hr.models import Payslip, PayslipItem, Payhead

        # ইতিমধ্যে payslip আছে কিনা
        payslip, _ = Payslip.objects.get_or_create(
            payroll=payroll,
            employee=employee,
            defaults={'basic_salary': employee.basic_salary},
        )

        # এই মাসের attendance summary নেওয়া
        attendance_summary = PayrollService._get_attendance_summary(employee, month_start)

        # Working days অনুযায়ী proportional salary
        if attendance_summary['working_days'] > 0:
            daily_rate = employee.basic_salary / attendance_summary['working_days']
            effective_basic = daily_rate * attendance_summary['present_days']
        else:
            effective_basic = employee.basic_salary

        # সব payhead calculate করা
        payheads = Payhead.objects.filter(is_active=True).order_by('sort_order')
        total_earning   = Decimal('0')
        total_deduction = Decimal('0')

        # আগের payslip items মুছে দেওয়া (regenerate)
        payslip.items.all().delete()

        for ph in payheads:
            if ph.calc_method == Payhead.CalcMethod.FIXED:
                amount = ph.default_amount
            else:
                # Percentage of basic salary
                amount = (effective_basic * ph.default_amount / 100).quantize(Decimal('0.01'))

            if amount == 0:
                continue

            PayslipItem.objects.create(payslip=payslip, payhead=ph, amount=amount)

            if ph.head_type == Payhead.HeadType.EARNING:
                total_earning += amount
            else:
                total_deduction += amount

        gross = effective_basic + total_earning
        net   = gross - total_deduction - payslip.advance_deduction - payslip.loan_deduction

        payslip.basic_salary     = effective_basic
        payslip.total_earning    = total_earning
        payslip.total_deduction  = total_deduction
        payslip.gross_salary     = gross
        payslip.net_salary       = max(0, net) + payslip.bonus
        payslip.working_days     = attendance_summary['working_days']
        payslip.present_days     = attendance_summary['present_days']
        payslip.absent_days      = attendance_summary['absent_days']
        payslip.leave_days       = attendance_summary['leave_days']
        payslip.overtime_hours   = attendance_summary['overtime_hours']
        payslip.save()

        return payslip

    @staticmethod
    def _get_attendance_summary(employee, month_start: date) -> dict:
        """একটি কর্মচারীর মাসিক attendance summary।"""
        from apps.hr.models import Attendance
        import calendar

        month_end = month_start + relativedelta(months=1) - relativedelta(days=1)

        # এই মাসের মোট working days (শনি-রবি বাদে, সরলীকৃত)
        total_days = calendar.monthrange(month_start.year, month_start.month)[1]
        # সরলীকৃত: সব দিনকে working day ধরা (পরে holiday ও weekend বাদ দেওয়া যাবে)
        working_days = total_days

        attendance_qs = Attendance.objects.filter(
            employee=employee,
            date__gte=month_start,
            date__lte=month_end,
        )

        present = attendance_qs.filter(
            status__in=[Attendance.AttendanceStatus.PRESENT,
                         Attendance.AttendanceStatus.LATE]
        ).count()

        half_day = attendance_qs.filter(status=Attendance.AttendanceStatus.HALF_DAY).count()
        leave    = attendance_qs.filter(status=Attendance.AttendanceStatus.ON_LEAVE).count()
        absent   = attendance_qs.filter(status=Attendance.AttendanceStatus.ABSENT).count()
        overtime = attendance_qs.aggregate(
            t=models_sum('overtime_hours')
        )['t'] or Decimal('0')

        effective_present = present + (half_day * Decimal('0.5'))

        return {
            'working_days': working_days,
            'present_days': effective_present,
            'absent_days': absent,
            'leave_days': leave,
            'overtime_hours': Decimal(str(overtime)),
        }

    @staticmethod
    @transaction.atomic
    def approve_payroll(payroll, approved_by) -> bool:
        """Payroll approve করা।"""
        from apps.hr.models import Payroll

        if payroll.status != Payroll.PayrollStatus.DRAFT:
            return False

        payroll.status      = Payroll.PayrollStatus.APPROVED
        payroll.approved_by = approved_by
        payroll.approved_at = timezone.now()
        payroll.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
        logger.info(f"Payroll approved: {payroll} by {approved_by}")
        return True

    @staticmethod
    @transaction.atomic
    def disburse_payroll(payroll) -> dict:
        """Payroll disburse (বেতন বিতরণ) করা — সব payslip paid mark করা।"""
        from apps.hr.models import Payroll, Payslip

        if payroll.status != Payroll.PayrollStatus.APPROVED:
            return {'success': False, 'error': 'Payroll must be approved first'}

        now = timezone.now()
        Payslip.objects.filter(payroll=payroll).update(is_paid=True, paid_at=now)

        payroll.status       = Payroll.PayrollStatus.DISBURSED
        payroll.disbursed_at = now
        payroll.save(update_fields=['status', 'disbursed_at', 'updated_at'])

        logger.info(f"Payroll disbursed: {payroll}")
        return {'success': True, 'disbursed_at': str(now)}


class AttendanceService:
    """Attendance record করা ও summary তৈরির service।"""

    @staticmethod
    @transaction.atomic
    def mark_attendance(employee, date_val: date, status: str,
                        check_in=None, check_out=None,
                        overtime_hours=0, note='', marked_by=None):
        """একটি কর্মচারীর একটি দিনের attendance record করা।"""
        from apps.hr.models import Attendance

        attendance, created = Attendance.objects.update_or_create(
            employee=employee,
            date=date_val,
            defaults={
                'status':         status,
                'check_in':       check_in,
                'check_out':      check_out,
                'overtime_hours': Decimal(str(overtime_hours)),
                'note':           note,
                'created_by':     marked_by,
            }
        )
        return attendance, created

    @staticmethod
    def bulk_mark_attendance(records: list, marked_by=None) -> dict:
        """
        একসাথে অনেক কর্মচারীর attendance mark করা।
        records = [{'employee_id': id, 'status': status, 'check_in': ..., ...}, ...]
        """
        from apps.hr.models import Employee
        success = 0
        errors  = []

        for r in records:
            try:
                emp = Employee.objects.get(pk=r['employee_id'])
                AttendanceService.mark_attendance(
                    employee=emp,
                    date_val=r.get('date', date.today()),
                    status=r['status'],
                    check_in=r.get('check_in'),
                    check_out=r.get('check_out'),
                    overtime_hours=r.get('overtime_hours', 0),
                    note=r.get('note', ''),
                    marked_by=marked_by,
                )
                success += 1
            except Exception as exc:
                errors.append({'record': r, 'error': str(exc)})

        return {'success': success, 'errors': errors}


def models_sum(field):
    from django.db.models import Sum
    return Sum(field)
