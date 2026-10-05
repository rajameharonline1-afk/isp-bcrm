# ফাইল: backend/apps/clients/filters.py
# Client queryset filter করার জন্য django-filter ব্যবহার করা হয়েছে।

import django_filters
from .models import Client


class ClientFilter(django_filters.FilterSet):
    """
    Client list-এ advanced filtering সুবিধা।
    Zone, status, expiry range, package ইত্যাদি দিয়ে filter করা যাবে।
    """
    # Date range filters
    expiry_date_from = django_filters.DateFilter(field_name='expiry_date', lookup_expr='gte')
    expiry_date_to   = django_filters.DateFilter(field_name='expiry_date', lookup_expr='lte')
    connection_from  = django_filters.DateFilter(field_name='connection_date', lookup_expr='gte')
    connection_to    = django_filters.DateFilter(field_name='connection_date', lookup_expr='lte')

    # Boolean filters
    optical_fiber  = django_filters.BooleanFilter()
    app_enabled    = django_filters.BooleanFilter()
    is_renewed     = django_filters.BooleanFilter()

    # Numeric range filters
    monthly_bill_min = django_filters.NumberFilter(field_name='monthly_bill', lookup_expr='gte')
    monthly_bill_max = django_filters.NumberFilter(field_name='monthly_bill', lookup_expr='lte')
    due_amount_min   = django_filters.NumberFilter(field_name='due_amount', lookup_expr='gte')

    class Meta:
        model  = Client
        fields = {
            'status':         ['exact'],
            'payment_status': ['exact'],
            'zone':           ['exact'],
            'subzone':        ['exact'],
            'box':            ['exact'],
            'thana':          ['exact'],
            'district':       ['exact'],
            'package':        ['exact'],
            'router':         ['exact'],
            'client_type':    ['exact'],
            'protocol':       ['exact'],
            'bill_date':      ['exact'],
        }
