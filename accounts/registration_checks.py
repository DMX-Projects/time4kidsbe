"""Shared checks for public parent self-registration flows."""

from __future__ import annotations

from django.contrib.auth import get_user_model

from accounts.models import UserRole

ALREADY_REGISTERED_MESSAGE = "This email is already registered."


def email_has_parent_account(email: str) -> bool:
    """True if a PARENT role user already uses this email."""
    normalized = (email or "").strip().lower()
    if not normalized or "@" not in normalized:
        return False

    User = get_user_model()
    for user in User.objects.filter(email__iexact=normalized).only("id", "email", "role"):
        if user.normalized_role() == UserRole.PARENT.value:
            return True
    return False
