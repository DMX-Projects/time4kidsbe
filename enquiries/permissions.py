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
    """Report ``?key=`` / header, or admin/approver JWT (optional Bearer)."""
    if _report_key_valid(request):
        return True
    return _jwt_admin_or_approver(request)


class CanViewLandingLeads:
    """DRF permission wrapper (kept for imports); prefer ``can_view_landing_leads()``."""

    def has_permission(self, request, view):
        return can_view_landing_leads(request)
