# ফাইল: backend/apps/accounts/views.py
# এই ফাইলটি user authentication, registration, profile management API views ধারণ করে।

from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import update_session_auth_hash
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import User, ActivityLog
from .serializers import (
    CustomTokenObtainPairSerializer,
    UserRegistrationSerializer,
    UserProfileSerializer,
    UserListSerializer,
    ChangePasswordSerializer,
    ActivityLogSerializer,
)
from .permissions import IsAdminUser, IsAdminOrStaff
from utils.pagination import StandardResultsSetPagination


@extend_schema(tags=['Authentication'])
class CustomTokenObtainPairView(TokenObtainPairView):
    """
    এই API দিয়ে user login করতে পারবে এবং JWT access token পাবে।
    Email + Password দিয়ে login করা হয়।
    """
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        # সফল login হলে activity log save করা
        if response.status_code == 200:
            user = User.objects.filter(email=request.data.get('email')).first()
            if user:
                ActivityLog.objects.create(
                    user=user,
                    action=ActivityLog.ActionType.LOGIN,
                    description='User logged in successfully.',
                    ip_address=self._get_client_ip(request),
                )
        return response

    def _get_client_ip(self, request):
        """Client-এর real IP address বের করা।"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')


@extend_schema(tags=['Authentication'])
class LogoutView(generics.GenericAPIView):
    """
    এই API দিয়ে user logout করতে পারবে।
    Refresh token blacklist-এ যোগ করা হবে।
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

            # Logout activity log save করা
            ActivityLog.objects.create(
                user=request.user,
                action=ActivityLog.ActionType.LOGOUT,
                description='User logged out.',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            return Response({'message': 'Successfully logged out.'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=['Users'])
class UserRegistrationView(generics.CreateAPIView):
    """
    এই API দিয়ে Admin নতুন user তৈরি করতে পারবে।
    শুধুমাত্র Admin role-এর user নতুন user তৈরি করতে পারবে।
    """
    serializer_class = UserRegistrationSerializer
    permission_classes = [IsAdminUser]

    def perform_create(self, serializer):
        user = serializer.save()
        # User তৈরির activity log save করা
        ActivityLog.objects.create(
            user=self.request.user,
            action=ActivityLog.ActionType.CREATE,
            model_name='User',
            object_id=str(user.id),
            description=f'New user created: {user.email}',
            ip_address=self.request.META.get('REMOTE_ADDR'),
        )


@extend_schema(tags=['Users'])
class UserProfileView(generics.RetrieveUpdateAPIView):
    """এই API দিয়ে user নিজের profile দেখতে এবং update করতে পারবে।"""
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


@extend_schema(tags=['Users'])
class ChangePasswordView(generics.UpdateAPIView):
    """এই API দিয়ে user নিজের password পরিবর্তন করতে পারবে।"""
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        # পুরনো password সঠিক কিনা চেক করা
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'old_password': 'পুরনো password সঠিক নয়।'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(serializer.validated_data['new_password'])
        user.save()

        return Response({'message': 'Password সফলভাবে পরিবর্তন হয়েছে।'}, status=status.HTTP_200_OK)


@extend_schema(tags=['Users'])
class UserManagementViewSet(viewsets.ModelViewSet):
    """
    এই API দিয়ে Admin সব user manage করতে পারবে।
    List, Create, Retrieve, Update, Delete সব operation support করে।
    """
    queryset = User.objects.all().order_by('-date_joined')
    permission_classes = [IsAdminUser]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['role', 'is_active']
    search_fields = ['email', 'username', 'full_name', 'phone']

    def get_serializer_class(self):
        if self.action == 'list':
            return UserListSerializer
        return UserProfileSerializer

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """User account activate/deactivate করার জন্য।"""
        user = self.get_object()
        user.is_active = not user.is_active
        user.save()

        status_text = 'activated' if user.is_active else 'deactivated'
        ActivityLog.objects.create(
            user=request.user,
            action=ActivityLog.ActionType.UPDATE,
            model_name='User',
            object_id=str(user.id),
            description=f'User {status_text}: {user.email}',
        )
        return Response({'message': f'User {status_text} successfully.', 'is_active': user.is_active})


@extend_schema(tags=['Activity Logs'])
class ActivityLogListView(generics.ListAPIView):
    """এই API দিয়ে Admin সব activity log দেখতে পারবে।"""
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAdminUser]
    pagination_class = StandardResultsSetPagination
    filterset_fields = ['action', 'model_name']
    search_fields = ['user__email', 'description']

    def get_queryset(self):
        return ActivityLog.objects.select_related('user').order_by('-created_at')
