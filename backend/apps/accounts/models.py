# ফাইল: backend/apps/accounts/models.py
# এই ফাইলটি ISP-BCRM সিস্টেমের সকল user accounts এবং role-based access control model ধারণ করে।

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom user manager - email দিয়ে user তৈরি করার জন্য।"""

    def create_user(self, email, username, password=None, **extra_fields):
        # Email validate করা
        if not email:
            raise ValueError('Email address অবশ্যই দিতে হবে।')
        if not username:
            raise ValueError('Username অবশ্যই দিতে হবে।')

        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        # Superuser-এর জন্য staff ও superuser flag সেট করা
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser-এর is_staff=True হতে হবে।')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser-এর is_superuser=True হতে হবে।')

        return self.create_user(email, username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    ISP-BCRM প্রজেক্টের Custom User Model।
    Role-based access control (Admin, Staff, Employee, Client) সমর্থন করে।
    """

    class Role(models.TextChoices):
        # ব্যবহারকারীর ভূমিকার তালিকা
        ADMIN = 'admin', 'Admin'
        STAFF = 'staff', 'Staff'
        EMPLOYEE = 'employee', 'Employee'
        CLIENT = 'client', 'Client'

    # মূল তথ্য
    email = models.EmailField(unique=True, verbose_name='Email Address')
    username = models.CharField(max_length=150, unique=True, verbose_name='Username')
    full_name = models.CharField(max_length=255, verbose_name='Full Name')
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name='Phone Number')

    # ভূমিকা (Role)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STAFF,
        verbose_name='User Role'
    )

    # Profile Photo
    photo = models.ImageField(upload_to='users/photos/', blank=True, null=True)

    # Account Status
    is_active = models.BooleanField(default=True, verbose_name='Is Active')
    is_staff = models.BooleanField(default=False, verbose_name='Is Staff')
    is_verified = models.BooleanField(default=False, verbose_name='Email Verified')

    # Timestamps
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    # Email দিয়ে login করা হবে
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'full_name']

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.full_name} ({self.email})"

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_employee(self):
        return self.role == self.Role.EMPLOYEE

    @property
    def is_client_user(self):
        return self.role == self.Role.CLIENT


class UserPermission(models.Model):
    """
    নির্দিষ্ট user-এর জন্য extra permissions।
    Role-এর বাইরে additional permission দেওয়ার জন্য ব্যবহৃত।
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='extra_permissions',
        verbose_name='User'
    )
    # Permission এর নাম (যেমন: can_approve_billing, can_manage_olt)
    permission_name = models.CharField(max_length=100, verbose_name='Permission Name')
    is_allowed = models.BooleanField(default=True, verbose_name='Is Allowed')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_permissions_extra'
        unique_together = ['user', 'permission_name']
        verbose_name = 'User Permission'

    def __str__(self):
        return f"{self.user.username} - {self.permission_name}"


class ActivityLog(models.Model):
    """
    সব user activity track করার জন্য Activity Log model।
    Admin dashboard-এ সব কার্যক্রম দেখা যাবে।
    """

    class ActionType(models.TextChoices):
        LOGIN = 'login', 'Login'
        LOGOUT = 'logout', 'Logout'
        CREATE = 'create', 'Create'
        UPDATE = 'update', 'Update'
        DELETE = 'delete', 'Delete'
        VIEW = 'view', 'View'
        EXPORT = 'export', 'Export'
        IMPORT = 'import', 'Import'

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='activity_logs'
    )
    action = models.CharField(max_length=20, choices=ActionType.choices)
    model_name = models.CharField(max_length=100, blank=True)  # কোন model-এ action করা হয়েছে
    object_id = models.CharField(max_length=50, blank=True)    # কোন object-এ action করা হয়েছে
    description = models.TextField(blank=True)                 # বিস্তারিত বিবরণ
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'activity_logs'
        verbose_name = 'Activity Log'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} - {self.action} - {self.created_at}"
