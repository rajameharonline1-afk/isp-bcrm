# ফাইল: backend/apps/system_config/serializers.py
# এই ফাইলটি system setting model-গুলোর serializer ধারণ করে; secret field কখনো response-এ যায় না।

from rest_framework import serializers
from .models import (
    CompanySetting, InvoiceSetting, EmailSetting, PaymentGateway,
    PaymentProcessingFee, SystemSetting,
)


class SecretWriteMixin:
    """
    Secret field গুলো শুধু লেখা যাবে (write_only), পড়া যাবে না।
    Update-এর সময় ফাঁকা পাঠালে আগের secret অপরিবর্তিত থাকবে।
    """
    secret_fields = ()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Secret সেট করা আছে কিনা frontend-কে শুধু তা জানানো হয়
        for field in self.secret_fields:
            data[f'{field}_set'] = bool(getattr(instance, field, ''))
        return data

    def update(self, instance, validated_data):
        for field in self.secret_fields:
            if not validated_data.get(field):
                validated_data.pop(field, None)
        return super().update(instance, validated_data)


class CompanySettingSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CompanySetting
        exclude = ['updated_by']


class InvoiceSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model  = InvoiceSetting
        exclude = ['updated_by']


class EmailSettingSerializer(SecretWriteMixin, serializers.ModelSerializer):
    secret_fields = ('password',)

    class Meta:
        model  = EmailSetting
        exclude = ['updated_by']
        extra_kwargs = {'password': {'write_only': True, 'required': False}}

    def validate(self, attrs):
        # TLS ও SSL একসাথে চালু থাকলে SMTP connection ব্যর্থ হয়
        if attrs.get('use_tls') and attrs.get('use_ssl'):
            raise serializers.ValidationError('Use either TLS or SSL, not both.')
        return attrs


class PaymentProcessingFeeSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PaymentProcessingFee
        fields = '__all__'

    def validate_value(self, value):
        if value < 0:
            raise serializers.ValidationError('Fee cannot be negative.')
        return value


class PaymentGatewaySerializer(SecretWriteMixin, serializers.ModelSerializer):
    secret_fields = ('store_password', 'api_key', 'api_secret')
    fees = PaymentProcessingFeeSerializer(many=True, read_only=True)

    class Meta:
        model  = PaymentGateway
        fields = '__all__'
        extra_kwargs = {f: {'write_only': True, 'required': False}
                        for f in ('store_password', 'api_key', 'api_secret')}


class SystemSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model  = SystemSetting
        exclude = ['updated_by']
