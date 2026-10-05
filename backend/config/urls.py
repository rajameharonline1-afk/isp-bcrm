# ফাইল: backend/config/urls.py
# এই ফাইলটি সমগ্র ISP-BCRM প্রজেক্টের সব API URL রুট একত্রিত করে।

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

# API Version Prefix
API_V1 = 'api/v1/'

urlpatterns = [
    # Django Admin Panel
    path('admin/', admin.site.urls),

    # API Documentation (Swagger & ReDoc)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Authentication API (Login, Logout, Token Refresh)
    path(API_V1 + 'auth/', include('apps.accounts.urls')),

    # Configuration API (Zone, Subzone, Package, etc.)
    path(API_V1 + 'config/', include('apps.configuration.urls')),

    # Client Management API
    path(API_V1 + 'clients/', include('apps.clients.urls')),

    # Billing API
    path(API_V1 + 'billing/', include('apps.billing.urls')),

    # Server & Mikrotik API
    path(API_V1 + 'servers/', include('apps.servers.urls')),

    # HR & Payroll API
    path(API_V1 + 'hr/', include('apps.hr.urls')),

    # OLT Management API
    path(API_V1 + 'olt/', include('apps.olt.urls')),

    # Network Diagram API
    path(API_V1 + 'network/', include('apps.network_diagram.urls')),

    # Leave Management API
    path(API_V1 + 'leave/', include('apps.leave.urls')),

    # MAC Reseller API
    path(API_V1 + 'mac-reseller/', include('apps.mac_reseller.urls')),

    # Support & Ticketing API
    path(API_V1 + 'support/', include('apps.support.urls')),

    # Task Management API
    path(API_V1 + 'tasks/', include('apps.tasks_management.urls')),

    # Bandwidth Buy API
    path(API_V1 + 'bandwidth/', include('apps.bandwidth.urls')),

    # Purchase API
    path(API_V1 + 'purchase/', include('apps.purchase.urls')),

    # Inventory API
    path(API_V1 + 'inventory/', include('apps.inventory.urls')),

    # Assets API
    path(API_V1 + 'assets/', include('apps.assets.urls')),

    # Sales & Service API
    path(API_V1 + 'sales/', include('apps.sales.urls')),

    # Income API
    path(API_V1 + 'income/', include('apps.income.urls')),

    # Expense API
    path(API_V1 + 'expense/', include('apps.expense.urls')),

    # Daily Account API
    path(API_V1 + 'daily-account/', include('apps.daily_account.urls')),

    # Accounting API
    path(API_V1 + 'accounting/', include('apps.accounting.urls')),

    # Reports API
    path(API_V1 + 'reports/', include('apps.reports.urls')),

    # SMS Service API
    path(API_V1 + 'sms/', include('apps.sms.urls')),

    # System Configuration API
    path(API_V1 + 'system/', include('apps.system_config.urls')),
]

# Development-এ Media files serve করা হবে
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
