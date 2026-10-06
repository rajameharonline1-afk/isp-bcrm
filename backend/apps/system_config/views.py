# ফাইল: backend/apps/system_config/views.py
# এই ফাইলটি System menu-র সব API (company, invoice, email, gateway, fee, system, auto process) ধারণ করে।

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django_celery_beat.models import PeriodicTask, CrontabSchedule

from apps.accounts.permissions import IsAdminUser
from apps.accounts.models import ActivityLog
from apps.accounts.serializers import ActivityLogSerializer
from utils.pagination import StandardResultsSetPagination
from .models import PaymentGateway, PaymentProcessingFee
from .serializers import (
    CompanySettingSerializer, InvoiceSettingSerializer, EmailSettingSerializer,
    PaymentGatewaySerializer, PaymentProcessingFeeSerializer, SystemSettingSerializer,
)
from .models import CompanySetting, InvoiceSetting, EmailSetting, SystemSetting
from .services import SystemConfigService


class SingletonSettingView(APIView):
    """
    একক-row setting (GET পড়া, PUT/PATCH আপডেট)।
    শুধু Admin পরিবর্তন করতে পারবে; অন্যরা পড়তে পারবে না কারণ email ইত্যাদি সংবেদনশীল।
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    model = None
    serializer_class = None

    def get(self, request):
        return Response(self.serializer_class(self.model.load()).data)

    def put(self, request):
        return self._save(request, partial=False)

    def patch(self, request):
        return self._save(request, partial=True)

    def _save(self, request, partial):
        serializer = self.serializer_class(self.model.load(), data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)


class CompanySettingView(SingletonSettingView):
    model, serializer_class = CompanySetting, CompanySettingSerializer


class InvoiceSettingView(SingletonSettingView):
    model, serializer_class = InvoiceSetting, InvoiceSettingSerializer


class SystemSettingView(SingletonSettingView):
    model, serializer_class = SystemSetting, SystemSettingSerializer


class EmailSettingView(SingletonSettingView):
    model, serializer_class = EmailSetting, EmailSettingSerializer

    def post(self, request):
        """Test email পাঠিয়ে SMTP setting যাচাই করা (body: {"to": "a@b.com"})।"""
        to = request.data.get('to') or request.user.email
        try:
            SystemConfigService.send_email('ISP-BCRM test email',
                                           'Your email settings are working.', to)
        except Exception as exc:
            return Response({'success': False, 'error': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'success': True, 'sent_to': to})


class PaymentGatewayViewSet(viewsets.ModelViewSet):
    """Payment gateway credentials পরিচালনা (শুধু Admin)।"""
    queryset           = PaymentGateway.objects.prefetch_related('fees')
    serializer_class   = PaymentGatewaySerializer
    permission_classes = [IsAuthenticated, IsAdminUser]


class PaymentProcessingFeeViewSet(viewsets.ModelViewSet):
    """Gateway-ভিত্তিক processing fee পরিচালনা।"""
    queryset           = PaymentProcessingFee.objects.select_related('gateway')
    serializer_class   = PaymentProcessingFeeSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    filterset_fields   = ['gateway', 'is_active']

    @action(detail=True, methods=['get'])
    def calculate(self, request, pk=None):
        """?amount=1000 দিলে এই fee-তে কত কাটা হবে তা দেখায়।"""
        try:
            fee = self.get_object().calculate(request.query_params.get('amount', 0))
        except Exception:
            return Response({'error': 'Invalid amount.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'fee': fee})


class AutomaticProcessViewSet(viewsets.ViewSet):
    """
    Automatic Process — Celery Beat-এর scheduled task দেখা, চালু/বন্ধ করা ও সময় বদলানো।
    Beat DatabaseScheduler ব্যবহার করে, তাই এখানে পরিবর্তন সাথে সাথে কার্যকর হয়।
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    @staticmethod
    def _row(task):
        cron = task.crontab
        return {
            'id': task.id, 'name': task.name, 'task': task.task, 'enabled': task.enabled,
            'schedule': str(cron) if cron else None,
            'minute': cron.minute if cron else None, 'hour': cron.hour if cron else None,
            'last_run_at': task.last_run_at, 'total_run_count': task.total_run_count,
        }

    def list(self, request):
        tasks = (PeriodicTask.objects.select_related('crontab')
                 .exclude(name='celery.backend_cleanup').order_by('name'))
        return Response([self._row(t) for t in tasks])

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        task = PeriodicTask.objects.get(pk=pk)
        task.enabled = not task.enabled
        task.save()
        return Response(self._row(task))

    @action(detail=True, methods=['post'])
    def reschedule(self, request, pk=None):
        """body: {"minute": "0", "hour": "6"} — দৈনিক নতুন সময়ে চালাবে।"""
        task = PeriodicTask.objects.select_related('crontab').get(pk=pk)
        if task.crontab is None:
            return Response({'error': 'This task does not use a cron schedule.'},
                            status=status.HTTP_400_BAD_REQUEST)
        minute = str(request.data.get('minute', task.crontab.minute))
        hour   = str(request.data.get('hour', task.crontab.hour))
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=minute, hour=hour, day_of_week=task.crontab.day_of_week,
            day_of_month=task.crontab.day_of_month, month_of_year=task.crontab.month_of_year,
            timezone=task.crontab.timezone,
        )
        task.crontab = schedule
        task.save()
        return Response(self._row(task))

    @action(detail=True, methods=['post'])
    def run_now(self, request, pk=None):
        """Task এখনই একবার চালানো।"""
        from config.celery import app
        task = PeriodicTask.objects.get(pk=pk)
        app.send_task(task.task)
        return Response({'queued': task.task})


class ActivityLoggerViewSet(viewsets.ReadOnlyModelViewSet):
    """Activity Loggers — সব user কার্যক্রমের তালিকা (শুধু পড়া)।"""
    queryset           = ActivityLog.objects.select_related('user')
    serializer_class   = ActivityLogSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class   = StandardResultsSetPagination
    filterset_fields   = ['user', 'action', 'model_name']
    search_fields      = ['description', 'user__email']
