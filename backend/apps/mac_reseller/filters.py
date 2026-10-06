# ফাইল: backend/apps/mac_reseller/filters.py
# এই ফাইলটি MAC Reseller API-এর filter class ধারণ করে।

import django_filters
from .models import (
    MACReseller, MACResellerFunding, ClientPGWPayment,
    PGWTransactionSettlement, MACResellerNotice,
)


class MACResellerFilter(django_filters.FilterSet):
    name   = django_filters.CharFilter(lookup_expr='icontains')
    status = django_filters.ChoiceFilter(choices=MACReseller.ResellerStatus.choices)

    class Meta:
        model  = MACReseller
        fields = ['status', 'name']


class FundingFilter(django_filters.FilterSet):
    reseller = django_filters.NumberFilter(field_name='reseller__id')
    status   = django_filters.ChoiceFilter(choices=MACResellerFunding.FundingStatus.choices)
    from_date = django_filters.DateFilter(field_name='funded_at__date', lookup_expr='gte')
    to_date   = django_filters.DateFilter(field_name='funded_at__date', lookup_expr='lte')

    class Meta:
        model  = MACResellerFunding
        fields = ['reseller', 'status', 'payment_method']


class PGWPaymentFilter(django_filters.FilterSet):
    reseller  = django_filters.NumberFilter(field_name='reseller__id')
    client    = django_filters.NumberFilter(field_name='client__id')
    status    = django_filters.ChoiceFilter(choices=ClientPGWPayment.PGWStatus.choices)
    gateway   = django_filters.ChoiceFilter(choices=ClientPGWPayment.PaymentGateway.choices)
    from_date = django_filters.DateFilter(field_name='created_at__date', lookup_expr='gte')
    to_date   = django_filters.DateFilter(field_name='created_at__date', lookup_expr='lte')

    class Meta:
        model  = ClientPGWPayment
        fields = ['reseller', 'client', 'status', 'gateway']


class SettlementFilter(django_filters.FilterSet):
    reseller = django_filters.NumberFilter(field_name='reseller__id')
    status   = django_filters.ChoiceFilter(choices=PGWTransactionSettlement.SettlementStatus.choices)
    from_date = django_filters.DateFilter(field_name='settlement_date', lookup_expr='gte')
    to_date   = django_filters.DateFilter(field_name='settlement_date', lookup_expr='lte')

    class Meta:
        model  = PGWTransactionSettlement
        fields = ['reseller', 'status']


class NoticeFilter(django_filters.FilterSet):
    notice_type = django_filters.ChoiceFilter(choices=MACResellerNotice.NoticeType.choices)
    is_active   = django_filters.BooleanFilter()

    class Meta:
        model  = MACResellerNotice
        fields = ['notice_type', 'is_active']
