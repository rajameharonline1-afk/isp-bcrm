# ফাইল: backend/apps/leave/views.py
# Leave Management module-এর API views।

from datetime import date
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.accounts.permissions import IsAdminOrStaff, IsAdminUser
from .models import LeaveCategory, LeaveSetup, LeaveBalance, LeaveApplication
from .serializers import (
    LeaveCategorySerializer, LeaveSetupSerializer,
    LeaveBalanceSerializer,
    LeaveApplicationListSerializer, LeaveApplicationDetailSerializer,
    LeaveApprovalSerializer,
)


class LeaveCategoryViewSet(viewsets.ModelViewSet):
    """ছুটির ধরন পরিচালনা।"""
    queryset           = LeaveCategory.objects.filter(is_active=True)
    serializer_class   = LeaveCategorySerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]


class LeaveSetupViewSet(viewsets.ModelViewSet):
    """Leave allocation rules পরিচালনা।"""
    queryset           = LeaveSetup.objects.select_related('category').filter(is_active=True)
    serializer_class   = LeaveSetupSerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['category', 'employment_type', 'fiscal_year']

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsAdminOrStaff])
    def allocate_to_all(self, request):
        """
        সব active employee-কে এই setup অনুযায়ী leave balance allocate করা।
        """
        from apps.hr.models import Employee
        fiscal_year = request.data.get('fiscal_year', '2026-2027')
        setups      = LeaveSetup.objects.filter(is_active=True, fiscal_year=fiscal_year)
        employees   = Employee.objects.filter(status=Employee.Status.ACTIVE)

        created = 0
        for emp in employees:
            for setup in setups:
                if setup.employment_type not in ('all', emp.employment_type):
                    continue
                _, is_new = LeaveBalance.objects.get_or_create(
                    employee=emp,
                    category=setup.category,
                    fiscal_year=fiscal_year,
                    defaults={
                        'total_days': setup.days_per_year,
                        'carry_forward_days': 0,
                    }
                )
                if is_new:
                    created += 1

        return Response({'created_balances': created, 'fiscal_year': fiscal_year})


class LeaveBalanceViewSet(viewsets.ReadOnlyModelViewSet):
    """কর্মচারীর leave balance দেখানো।"""
    queryset = LeaveBalance.objects.select_related(
        'employee', 'category',
    ).order_by('employee__full_name', 'category__name')

    serializer_class   = LeaveBalanceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['employee', 'category', 'fiscal_year']


class LeaveApplicationViewSet(viewsets.ModelViewSet):
    """ছুটির আবেদন পরিচালনা।"""
    queryset = LeaveApplication.objects.select_related(
        'employee', 'category', 'reviewed_by',
    ).order_by('-applied_at')

    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields   = ['status', 'category', 'employee']
    search_fields      = ['employee__full_name', 'reason']
    ordering_fields    = ['start_date', 'applied_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return LeaveApplicationListSerializer
        return LeaveApplicationDetailSerializer

    def perform_create(self, serializer):
        # Employee profile খোঁজা
        try:
            emp = self.request.user.employee_profile
        except Exception:
            from rest_framework.exceptions import ValidationError
            raise ValidationError("You do not have an employee profile.")
        serializer.save(employee=emp)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminOrStaff])
    def review(self, request, pk=None):
        """ছুটির আবেদন approve বা reject করা।"""
        application = self.get_object()
        serializer  = LeaveApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action_val  = serializer.validated_data['action']
        review_note = serializer.validated_data.get('review_note', '')

        if application.status != LeaveApplication.Status.PENDING:
            return Response({'error': 'Only pending applications can be reviewed'}, status=400)

        application.reviewed_by  = request.user
        application.reviewed_at  = timezone.now()
        application.review_note  = review_note

        if action_val == 'approve':
            application.status = LeaveApplication.Status.APPROVED
            # Leave balance আপডেট করা
            balance = LeaveBalance.objects.filter(
                employee=application.employee,
                category=application.category,
            ).first()
            if balance:
                balance.used_days += application.total_days
                balance.save(update_fields=['used_days', 'updated_at'])

            # Attendance-এ leave mark করা (এই তারিখ range-এ)
            _mark_leave_in_attendance(application)

        else:
            application.status = LeaveApplication.Status.REJECTED

        application.save()
        return Response({'success': True, 'status': application.status})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """ছুটির আবেদন cancel করা (কর্মচারী নিজে করতে পারবে)।"""
        application = self.get_object()

        # নিজের application cancel করা যাবে
        try:
            is_own = (request.user.employee_profile == application.employee)
        except Exception:
            is_own = False

        if not is_own and not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=403)

        if application.status not in (
            LeaveApplication.Status.PENDING,
            LeaveApplication.Status.APPROVED,
        ):
            return Response({'error': 'Cannot cancel this application'}, status=400)

        application.status = LeaveApplication.Status.CANCELLED
        application.save(update_fields=['status', 'updated_at'])
        return Response({'success': True})


def _mark_leave_in_attendance(application):
    """
    Approved leave-এর দিনগুলো attendance-এ ON_LEAVE mark করা।
    """
    from apps.hr.models import Attendance
    from datetime import timedelta

    current = application.start_date
    while current <= application.end_date:
        Attendance.objects.update_or_create(
            employee=application.employee,
            date=current,
            defaults={'status': Attendance.AttendanceStatus.ON_LEAVE},
        )
        current += timedelta(days=1)
