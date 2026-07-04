import secrets

from django.conf import settings

from accounts.models import UserRole
from accounts.permissions import _norm_role


def _report_key_from_request(request) -> str:
    return (
        request.headers.get("X-Landing-Leads-Key")
        or request.query_params.get("key")
        or ""
    ).strip()


def _report_key_valid(request) -> bool:
    expected = (getattr(settings, "LANDING_LEADS_REPORT_KEY", None) or "").strip()
    if not expected:
        return False
    provided = _report_key_from_request(request)
    return bool(provided and secrets.compare_digest(provided, expected))


def _jwt_admin_or_approver(request) -> bool:
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False
    role = _norm_role(user)
    return role in (UserRole.ADMIN.value, UserRole.APPROVER.value)


def can_view_landing_leads(request) -> bool:
    """Report ``?key=`` / header, admin/approver JWT, or CRM user."""
    if _report_key_valid(request):
        return True
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False
    role = _norm_role(user)
    return role in (UserRole.ADMIN.value, UserRole.APPROVER.value, UserRole.CRM.value)


class CanViewLandingLeads:
    """DRF permission wrapper (kept for imports); prefer ``can_view_landing_leads()``."""

    def has_permission(self, request, view):
        return can_view_landing_leads(request)


def can_view_crm_leads(request) -> bool:
    """
    CRM leads report access — deliberately separate from website admins.

    CRM users can see the CRM dashboard. Django superusers retain owner access.
    Regular ADMIN-role users do NOT get access here, so the CRM stays isolated
    from the existing admin team.
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return False
    return bool(_norm_role(user) == UserRole.CRM.value or getattr(user, "is_superuser", False))


class CanViewCrmLeads:
    """DRF permission wrapper for the CRM leads report."""

    def has_permission(self, request, view):
        return can_view_crm_leads(request)
