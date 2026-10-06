# ফাইল: backend/apps/sms/serializers.py
# এই ফাইলটি SMS Gateway, Template, Group, Message ও send request-এর serializer ধারণ করে।

from rest_framework import serializers
from apps.system_config.serializers import SecretWriteMixin
from .models import SMSGateway, SMSTemplate, SMSGroup, SMSMessage


class SMSGatewaySerializer(SecretWriteMixin, serializers.ModelSerializer):
    secret_fields = ('api_key', 'secret_key')

    class Meta:
        model  = SMSGateway
        fields = '__all__'
        extra_kwargs = {'api_key': {'write_only': True, 'required': False},
                        'secret_key': {'write_only': True, 'required': False}}

    def validate_params_template(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('Must be a JSON object.')
        return value


class SMSTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SMSTemplate
        fields = '__all__'


class SMSGroupSerializer(serializers.ModelSerializer):
    client_count = serializers.IntegerField(source='clients.count', read_only=True)

    class Meta:
        model  = SMSGroup
        fields = '__all__'


class SMSMessageSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.full_name', read_only=True, default='')

    class Meta:
        model  = SMSMessage
        exclude = ['gateway']
        read_only_fields = [f.name for f in SMSMessage._meta.fields]


class SendSMSSerializer(serializers.Serializer):
    """Individual SMS: একটি নম্বরে বার্তা (সরাসরি লেখা বা template থেকে)।"""
    phone    = serializers.CharField()
    message  = serializers.CharField(required=False, allow_blank=True)
    template = serializers.PrimaryKeyRelatedField(queryset=SMSTemplate.objects.filter(is_active=True),
                                                  required=False)

    def validate(self, attrs):
        if not attrs.get('message') and not attrs.get('template'):
            raise serializers.ValidationError('Provide a message or a template.')
        return attrs


class BulkSMSSerializer(serializers.Serializer):
    """Send SMS: group, client তালিকা বা zone/status filter দিয়ে একসাথে অনেককে।"""
    message  = serializers.CharField(required=False, allow_blank=True)
    template = serializers.PrimaryKeyRelatedField(queryset=SMSTemplate.objects.filter(is_active=True),
                                                  required=False)
    group    = serializers.PrimaryKeyRelatedField(queryset=SMSGroup.objects.all(), required=False)
    clients  = serializers.ListField(child=serializers.IntegerField(), required=False)
    zone     = serializers.IntegerField(required=False)
    status   = serializers.CharField(required=False)

    def validate(self, attrs):
        if not attrs.get('message') and not attrs.get('template'):
            raise serializers.ValidationError('Provide a message or a template.')
        if not any(attrs.get(k) for k in ('group', 'clients', 'zone', 'status')):
            raise serializers.ValidationError('Choose recipients: group, clients, zone or status.')
        return attrs
