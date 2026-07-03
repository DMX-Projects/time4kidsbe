from rest_framework.permissions import BasePermission

from .models import UserRole


def _norm_role(user) -> str:
    """Legacy DB dumps sometimes store roles in lowercase; Django choices are uppercase."""
    return str(getattr(user, "role", "") or "").strip().upper()


class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and _norm_role(request.user) == UserRole.ADMIN.value
        )


class IsAdminOrApproverUser(BasePermission):
    """Head office: full admin or approver-only (social + indents)."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        r = _norm_role(request.user)
        return r in (UserRole.ADMIN.value, UserRole.APPROVER.value)


class IsCrmUser(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and _norm_role(request.user) == UserRole.CRM.value
        )


class IsFranchiseUser(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and _norm_role(request.user) == UserRole.FRANCHISE.value
        )


class IsParentUser(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and _norm_role(request.user) == UserRole.PARENT.value
        )


class IsDriverUser(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and _norm_role(request.user) == UserRole.DRIVER.value
        )
