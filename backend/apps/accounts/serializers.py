# ফাইল: backend/apps/accounts/serializers.py
# এই ফাইলটি User authentication, registration এবং profile serializers ধারণ করে।

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from .models import User, ActivityLog, UserPermission


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    JWT token এ extra user information যোগ করার জন্য custom serializer।
    Login করলে token-এর সাথে user details পাওয়া যাবে।
    """

    @classmethod
    def get_token(cls, user):
        # Parent class-এর token নেওয়া
        token = super().get_token(user)

        # Token-এ extra claims যোগ করা
        token['user_id'] = user.id
        token['email'] = user.email
        token['username'] = user.username
        token['full_name'] = user.full_name
        token['role'] = user.role

        return token

    def validate(self, attrs):
        # Email দিয়ে login করার জন্য username field-এ email নেওয়া হচ্ছে
        data = super().validate(attrs)

        # Response-এ extra user information যোগ করা
        data['user'] = {
            'id': self.user.id,
            'email': self.user.email,
            'username': self.user.username,
            'full_name': self.user.full_name,
            'role': self.user.role,
            'photo': self.user.photo.url if self.user.photo else None,
        }
        return data


class UserRegistrationSerializer(serializers.ModelSerializer):
    """নতুন user রেজিস্ট্রেশনের জন্য serializer।"""

    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'username', 'full_name', 'phone', 'role', 'password', 'password_confirm']

    def validate(self, attrs):
        # দুটো password মিলছে কিনা চেক করা
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password': 'Password দুটো মিলছে না।'})
        return attrs

    def create(self, validated_data):
        # password_confirm field সরিয়ে user তৈরি করা
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """User profile দেখা এবং update করার জন্য serializer।"""

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'full_name', 'phone',
            'role', 'photo', 'is_active', 'is_verified',
            'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'email', 'role', 'is_verified', 'date_joined', 'last_login']


class UserListSerializer(serializers.ModelSerializer):
    """User list দেখার জন্য সংক্ষিপ্ত serializer।"""

    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'full_name', 'phone', 'role', 'is_active', 'date_joined']


class ChangePasswordSerializer(serializers.Serializer):
    """Password পরিবর্তনের জন্য serializer।"""

    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    confirm_password = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'new_password': 'নতুন password দুটো মিলছে না।'})
        return attrs


class ActivityLogSerializer(serializers.ModelSerializer):
    """Activity log দেখার জন্য serializer।"""

    user_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = ActivityLog
        fields = ['id', 'user', 'user_name', 'action', 'model_name', 'object_id',
                  'description', 'ip_address', 'created_at']
