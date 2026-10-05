# ফাইল: backend/apps/servers/urls.py
# এই ফাইলটি servers app-এর সব URL routes ধারণ করে।

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MikrotikRouterViewSet,
    RadiusServerViewSet,
    RouterConnectionLogListView,
    RouterBackupListView,
    RadiusUserInfoView,
    RadiusActiveSessionsView,
)

router = DefaultRouter()
router.register('routers', MikrotikRouterViewSet, basename='mikrotik-routers')
router.register('radius-servers', RadiusServerViewSet, basename='radius-servers')

urlpatterns = [
    path('', include(router.urls)),

    # Router logs
    path('logs/', RouterConnectionLogListView.as_view(), name='router-logs'),

    # Router backups
    path('backups/', RouterBackupListView.as_view(), name='router-backups'),

    # RADIUS user info
    path('radius/user/<str:username>/', RadiusUserInfoView.as_view(), name='radius-user-info'),

    # RADIUS active sessions
    path('radius/active-sessions/', RadiusActiveSessionsView.as_view(), name='radius-active-sessions'),
]
