# ফাইল: backend/apps/billing/filters.py
import django_filters
from .models import Billing, Payment


class BillingFilter(django_filters.FilterSet):
    bill_month_from = django_filters.DateFilter(field_name='bill_month', lookup_expr='gte')
    bill_month_to   = django_filters.DateFilter(field_name='bill_month', lookup_expr='lte')
    due_date_from   = django_filters.DateFilter(field_name='due_date', lookup_expr='gte')
    due_date_to     = django_filters.DateFilter(field_name='due_date', lookup_expr='lte')
    amount_min      = django_filters.NumberFilter(field_name='payable_amount', lookup_expr='gte')
    amount_max      = django_filters.NumberFilter(field_name='payable_amount', lookup_expr='lte')

    class Meta:
        model  = Billing
        fields = {'status': ['exact'], 'client': ['exact']}


class PaymentFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name='payment_date', lookup_expr='gte')
    date_to   = django_filters.DateFilter(field_name='payment_date', lookup_expr='lte')

    class Meta:
        model  = Payment
        fields = {'method': ['exact'], 'client': ['exact'], 'collected_by': ['exact']}
