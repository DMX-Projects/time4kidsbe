from rest_framework.permissions import BasePermission

from .models import UserRole


class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == UserRole.ADMIN)


class IsAdminOrApproverUser(BasePermission):
    """Head office: full admin or approver-only (social + indents)."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in (UserRole.ADMIN, UserRole.APPROVER)


class IsFranchiseUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == UserRole.FRANCHISE)


class IsParentUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == UserRole.PARENT)


class IsDriverUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == UserRole.DRIVER)
