# ফাইল: backend/apps/accounts/permissions.py
# এই ফাইলটি ISP-BCRM প্রজেক্টের role-based permission classes ধারণ করে।

from rest_framework.permissions import BasePermission


class IsAdminUser(BasePermission):
    """শুধুমাত্র Admin role-এর user access পাবে।"""
    message = 'এই action-এর জন্য Admin permission প্রয়োজন।'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'admin')


class IsAdminOrStaff(BasePermission):
    """Admin এবং Staff উভয় role access পাবে।"""
    message = 'এই action-এর জন্য Admin বা Staff permission প্রয়োজন।'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['admin', 'staff']
        )


class IsEmployeeOrAbove(BasePermission):
    """Employee, Staff এবং Admin সবাই access পাবে (Client ছাড়া)।"""
    message = 'এই action-এর জন্য Employee বা উপরের role প্রয়োজন।'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role in ['admin', 'staff', 'employee']
        )


class IsClientUser(BasePermission):
    """শুধুমাত্র Client role-এর user access পাবে (Client Portal-এর জন্য)।"""
    message = 'এই section শুধুমাত্র Client-দের জন্য।'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            request.user.role == 'client'
        )


class IsOwnerOrAdmin(BasePermission):
    """নিজের data বা Admin access পাবে।"""
    message = 'শুধুমাত্র নিজের data বা Admin access করতে পারবে।'

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True
        # Object-এর owner কিনা চেক করা
        return obj == request.user or getattr(obj, 'user', None) == request.user
