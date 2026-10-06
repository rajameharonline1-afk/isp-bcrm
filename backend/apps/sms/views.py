# ফাইল: backend/apps/sms/views.py
# এই ফাইলটি SMS Service menu-র API (Gateway, Template, Group, Send SMS, Messages Report) ধারণ করে।

from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.accounts.permissions import IsAdminUser, IsAdminOrStaff
from apps.clients.models import Client
from utils.pagination import StandardResultsSetPagination
from .models import SMSGateway, SMSTemplate, SMSGroup, SMSMessage
from .serializers import (
    SMSGatewaySerializer, SMSTemplateSerializer, SMSGroupSerializer,
    SMSMessageSerializer, SendSMSSerializer, BulkSMSSerializer,
)
from .services import SMSService


class SMSGatewayViewSet(viewsets.ModelViewSet):
    """SMS Gateway পরিচালনা — credentials থাকায় শুধু Admin।"""
    queryset           = SMSGateway.objects.all()
    serializer_class   = SMSGatewaySerializer
    permission_classes = [IsAuthenticated, IsAdminUser]


class SMSTemplateViewSet(viewsets.ModelViewSet):
    """SMS Template পরিচালনা।"""
    queryset           = SMSTemplate.objects.all()
    serializer_class   = SMSTemplateSerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    filterset_fields   = ['event', 'is_active']


class SMSGroupViewSet(viewsets.ModelViewSet):
    """SMS Group পরিচালনা।"""
    queryset           = SMSGroup.objects.prefetch_related('clients')
    serializer_class   = SMSGroupSerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]


class SMSMessageViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """পাঠানো SMS-এর log (Messages Report) এবং SMS পাঠানোর action।"""
    queryset           = SMSMessage.objects.select_related('client')
    serializer_class   = SMSMessageSerializer
    permission_classes = [IsAuthenticated, IsAdminOrStaff]
    pagination_class   = StandardResultsSetPagination
    filter_backends    = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields   = ['status', 'client', 'template']
    search_fields      = ['recipient', 'message']
    ordering_fields    = ['created_at']

    @action(detail=False, methods=['post'])
    def send(self, request):
        """Individual SMS — একটি নম্বরে পাঠানো।"""
        ser = SendSMSSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        template = ser.validated_data.get('template')
        body = ser.validated_data.get('message') or template.body
        try:
            sms = SMSService.queue(ser.validated_data['phone'], body,
                                   template=template, sent_by=request.user)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if sms is None:
            return Response({'error': 'SMS service is disabled in system settings.'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(SMSMessageSerializer(sms).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def send_bulk(self, request):
        """Send SMS — group/client/zone/status অনুযায়ী অনেককে; template হলে প্রত্যেকের নামে render হয়।"""
        ser = BulkSMSSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        template = d.get('template')
        body = d.get('message') or template.body

        qs = Client.objects.exclude(status=Client.Status.LEFT)
        extra_numbers = []
        if d.get('group'):
            qs = qs.filter(sms_groups=d['group'])
            raw = d['group'].extra_numbers.replace(',', '\n').split()
            extra_numbers = [n for n in raw if n]
        if d.get('clients'):
            qs = qs.filter(id__in=d['clients'])
        if d.get('zone'):
            qs = qs.filter(zone_id=d['zone'])
        if d.get('status'):
            qs = qs.filter(status=d['status'])

        queued, skipped = 0, []
        for client in qs.distinct():
            try:
                text = SMSService.render(body, SMSService.client_context(client))
                SMSService.queue(client.phone, text, client=client, template=template,
                                 sent_by=request.user)
                queued += 1
            except ValueError:
                skipped.append(client.phone)
        for number in extra_numbers:
            try:
                SMSService.queue(number, SMSService.render(body, {}), template=template,
                                 sent_by=request.user)
                queued += 1
            except ValueError:
                skipped.append(number)
        return Response({'queued': queued, 'skipped_invalid': skipped})

    @action(detail=True, methods=['post'])
    def resend(self, request, pk=None):
        """ব্যর্থ SMS আবার পাঠানো।"""
        sms = self.get_object()
        if sms.status == SMSMessage.Status.SENT:
            return Response({'error': 'Already sent.'}, status=status.HTTP_400_BAD_REQUEST)
        from .tasks import send_sms_task
        sms.status = SMSMessage.Status.PENDING
        sms.save(update_fields=['status'])
        send_sms_task.delay(sms.id)
        return Response({'queued': sms.id})
