# ফাইল: backend/apps/hr/views.py
# HR & Payroll module-এর সব API views।

import logging
from datetime import date
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.shortcuts import get_object_or_404

from apps.accounts.permissions import IsAdminOrStaff, IsAdminUser
from .models import (
    Department, Position, Employee, Payhead,
    Payroll, Payslip, Attendance,
    ResignRule, Resignation, Rejoin,
)
from .serializers import (
    DepartmentSerializer, PositionSerializer,
    EmployeeListSerializer, EmployeeDetailSerializer, EmployeeCreateSerializer,
    PayheadSerializer, PayrollListSerializer, PayrollDetailSerializer,
    PayslipSerializer, AttendanceSerializer, BulkAttendanceSerializer,
    ResignRuleSerializer, ResignationSerializer, RejoinSerializer,
)
from .services import PayrollService, AttendanceService

logger = logging.getLogger(__name__)


class DepartmentViewSet(viewsets.ModelViewSet):
    """বিভাগ পরিচালনা।"""
    queryset           = Department.objects.prefetch_related('positions')
    serializer_class   = DepartmentSerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [SearchFilter]
    search_fields      = ['name']


class PositionViewSet(viewsets.ModelViewSet):
    """পদবি পরিচালনা।"""
    queryset           = Position.objects.select_related('department')
    serializer_class   = PositionSerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [DjangoFilterBackend, SearchFilter]
    filterset_fields   = ['department', 'is_active']
    search_fields      = ['name']


class EmployeeViewSet(viewsets.ModelViewSet):
    """কর্মচারী পরিচালনা।"""
    queryset = Employee.objects.select_related(
        'department', 'position', 'reporting_to', 'user', 'created_by',
    ).order_by('full_name')

    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields   = ['department', 'position', 'status', 'employment_type']
    search_fields      = ['full_name', 'employee_id', 'phone', 'email', 'nid']
    ordering_fields    = ['full_name', 'joining_date', 'basic_salary', 'created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return EmployeeListSerializer
        if self.action in ('create', 'update', 'partial_update'):
            return EmployeeCreateSerializer
        return EmployeeDetailSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def payslips(self, request, pk=None):
        """কর্মচারীর সব payslip।"""
        employee = self.get_object()
        slips    = Payslip.objects.filter(employee=employee).select_related('payroll').order_by('-payroll__month')
        serializer = PayslipSerializer(slips, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def attendance_summary(self, request, pk=None):
        """কর্মচারীর মাসিক attendance summary।"""
        employee    = self.get_object()
        month_param = request.query_params.get('month', str(date.today())[:7])
        try:
            month = date.fromisoformat(month_param + '-01')
        except ValueError:
            month = date.today().replace(day=1)

        summary = PayrollService._get_attendance_summary(employee, month)
        return Response(summary)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """কর্মচারী statistics।"""
        from django.db.models import Count
        data = {
            'total':          Employee.objects.count(),
            'active':         Employee.objects.filter(status=Employee.Status.ACTIVE).count(),
            'resigned':       Employee.objects.filter(status=Employee.Status.RESIGNED).count(),
            'by_department':  list(
                Employee.objects.filter(status=Employee.Status.ACTIVE)
                .values('department__name').annotate(count=Count('id')).order_by('-count')
            ),
        }
        return Response(data)


class PayheadViewSet(viewsets.ModelViewSet):
    """বেতনের component পরিচালনা।"""
    queryset           = Payhead.objects.all().order_by('sort_order', 'name')
    serializer_class   = PayheadSerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['head_type', 'is_active']


class PayrollViewSet(viewsets.ModelViewSet):
    """মাসিক payroll পরিচালনা।"""
    queryset = Payroll.objects.prefetch_related('payslips__employee').order_by('-month')
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [DjangoFilterBackend, OrderingFilter]
    filterset_fields   = ['status']
    ordering_fields    = ['month', 'created_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PayrollDetailSerializer
        return PayrollListSerializer

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsAdminOrStaff])
    def generate(self, request):
        """
        নির্দিষ্ট মাসের payroll generate করা।
        সব active employee-র payslip তৈরি করে।
        """
        month_str = request.data.get('month')
        if not month_str:
            return Response({'error': 'month is required (YYYY-MM)'}, status=400)
        try:
            month = date.fromisoformat(month_str + '-01')
        except ValueError:
            return Response({'error': 'Invalid month format (YYYY-MM)'}, status=400)

        payroll, created, skipped = PayrollService.generate_payroll(
            month=month, created_by=request.user,
        )
        return Response({
            'payroll':  PayrollDetailSerializer(payroll).data,
            'created':  created,
            'skipped':  skipped,
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def approve(self, request, pk=None):
        """Payroll approve করা।"""
        payroll = self.get_object()
        success = PayrollService.approve_payroll(payroll, approved_by=request.user)
        if not success:
            return Response({'error': 'Only Draft payroll can be approved'}, status=400)
        return Response({'success': True, 'status': payroll.status})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def disburse(self, request, pk=None):
        """Payroll disburse (বেতন বিতরণ) করা।"""
        payroll = self.get_object()
        result  = PayrollService.disburse_payroll(payroll)
        if not result['success']:
            return Response(result, status=400)
        return Response(result)

    @action(detail=True, methods=['get'])
    def salary_sheet(self, request, pk=None):
        """Payroll-এর salary sheet (সব payslip) দেখানো।"""
        payroll    = self.get_object()
        payslips   = payroll.payslips.select_related(
            'employee__department', 'employee__position',
        ).prefetch_related('items__payhead').order_by('employee__full_name')
        serializer = PayslipSerializer(payslips, many=True)
        return Response({
            'payroll': PayrollListSerializer(payroll).data,
            'payslips': serializer.data,
        })


class AttendanceViewSet(viewsets.ModelViewSet):
    """উপস্থিতি পরিচালনা।"""
    queryset = Attendance.objects.select_related(
        'employee__department', 'created_by',
    ).order_by('-date', 'employee__full_name')

    serializer_class   = AttendanceSerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields   = ['employee', 'status', 'date']
    search_fields      = ['employee__full_name', 'employee__employee_id']
    ordering_fields    = ['date', 'created_at']

    @action(detail=False, methods=['post'])
    def bulk_mark(self, request):
        """একসাথে অনেক কর্মচারীর attendance mark করা।"""
        serializer = BulkAttendanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        records  = []
        att_date = serializer.validated_data['date']
        for r in serializer.validated_data['records']:
            r['date'] = att_date
            records.append(r)

        result = AttendanceService.bulk_mark_attendance(records, marked_by=request.user)
        return Response(result)

    @action(detail=False, methods=['get'])
    def today(self, request):
        """আজকের attendance summary।"""
        from django.db.models import Count
        today  = date.today()
        total  = Employee.objects.filter(status=Employee.Status.ACTIVE).count()
        by_status = Attendance.objects.filter(date=today).values('status').annotate(count=Count('id'))
        return Response({'date': str(today), 'total_employees': total, 'by_status': list(by_status)})


class ResignRuleViewSet(viewsets.ModelViewSet):
    """পদত্যাগের নিয়ম পরিচালনা।"""
    queryset           = ResignRule.objects.filter(is_active=True)
    serializer_class   = ResignRuleSerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]


class ResignationViewSet(viewsets.ModelViewSet):
    """পদত্যাগ / বরখাস্ত পরিচালনা।"""
    queryset = Resignation.objects.select_related(
        'employee', 'resign_rule', 'approved_by',
    ).order_by('-apply_date')

    serializer_class   = ResignationSerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['status', 'resign_type', 'employee']

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def approve(self, request, pk=None):
        """পদত্যাগ আবেদন approve করা।"""
        from django.utils import timezone
        resignation = self.get_object()

        # Settlement calculate করা
        resignation.status      = Resignation.Status.APPROVED
        resignation.approved_by = request.user
        resignation.approved_at = timezone.now()
        resignation.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])

        # Employee-এর status পরিবর্তন করা
        emp = resignation.employee
        emp.status = Employee.Status.RESIGNED
        emp.save(update_fields=['status', 'updated_at'])

        return Response({'success': True})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def reject(self, request, pk=None):
        """পদত্যাগ আবেদন reject করা।"""
        from django.utils import timezone
        resignation = self.get_object()
        resignation.status      = Resignation.Status.REJECTED
        resignation.approved_by = request.user
        resignation.approved_at = timezone.now()
        resignation.note        = request.data.get('note', '')
        resignation.save(update_fields=['status', 'approved_by', 'approved_at', 'note', 'updated_at'])
        return Response({'success': True})


class RejoinViewSet(viewsets.ModelViewSet):
    """পুনরায় যোগদান পরিচালনা।"""
    queryset = Rejoin.objects.select_related(
        'employee', 'department', 'position', 'approved_by',
    ).order_by('-rejoin_date')

    serializer_class   = RejoinSerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def perform_create(self, serializer):
        rejoin = serializer.save(approved_by=self.request.user)
        # Employee-এর status ও department আপডেট করা
        emp = rejoin.employee
        emp.status       = Employee.Status.ACTIVE
        emp.department   = rejoin.department
        emp.position     = rejoin.position
        emp.basic_salary = rejoin.new_basic_salary
        emp.save(update_fields=['status', 'department', 'position', 'basic_salary', 'updated_at'])
