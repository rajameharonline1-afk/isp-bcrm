# ফাইল: backend/apps/accounts/urls.py
# এই ফাইলটি accounts app-এর সব URL routes ধারণ করে।

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    CustomTokenObtainPairView,
    LogoutView,
    UserRegistrationView,
    UserProfileView,
    ChangePasswordView,
    UserManagementViewSet,
    ActivityLogListView,
)

# ViewSet-এর জন্য Router ব্যবহার
router = DefaultRouter()
router.register('users', UserManagementViewSet, basename='user-management')

urlpatterns = [
    # Login endpoint - JWT token পাওয়ার জন্য
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),

    # Token refresh - Access token নবায়নের জন্য
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Logout endpoint
    path('logout/', LogoutView.as_view(), name='logout'),

    # User registration (Admin only)
    path('register/', UserRegistrationView.as_view(), name='user_register'),

    # Current user-এর profile
    path('profile/', UserProfileView.as_view(), name='user_profile'),

    # Password পরিবর্তন
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),

    # Activity logs (Admin only)
    path('activity-logs/', ActivityLogListView.as_view(), name='activity_logs'),

    # User management (Admin only) - router-generated URLs
    path('', include(router.urls)),
]
