"""Transactional emails for accounts (password reset via SendGrid)."""

from __future__ import annotations

import html
import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes

from common.form_emails import centre_details_from_franchise, send_personal_thankyou
from common.sendgrid_email import default_from_email, send_sendgrid_message, sendgrid_api_key
from django.utils.http import urlsafe_base64_encode

logger = logging.getLogger(__name__)


def build_password_reset_url(user) -> str:
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    frontend_base = (getattr(settings, "PUBLIC_SITE_URL", "") or "").strip().rstrip("/")
    if not frontend_base:
        frontend_base = "http://localhost:3000"
    return f"{frontend_base}/reset-password?uid={uidb64}&token={token}"


def personal_email_for_user(user, *, preferred: str | None = None) -> str:
    """
    Best personal inbox for this account (never HQ / enquiry inboxes).
    Order: typed email on forgot form → User.email → ParentProfile.Emailid → child Emailid.
    """
    preferred = (preferred or "").strip()
    if preferred and "@" in preferred:
        return preferred

    account_email = (getattr(user, "email", None) or "").strip()
    if account_email and "@" in account_email:
        return account_email

    from accounts.profile_access import parent_profile_for_user

    pp = parent_profile_for_user(user)
    if pp:
        legacy_parent = (getattr(pp, "Emailid", None) or "").strip()
        if legacy_parent and "@" in legacy_parent:
            return legacy_parent

        from students.models import StudentProfile

        for student in StudentProfile.objects.filter(parent=pp).only("Emailid").order_by("id"):
            student_email = (getattr(student, "Emailid", None) or "").strip()
            if student_email and "@" in student_email:
                return student_email

    return ""


def find_user_for_password_reset(identifier: str):
    """Resolve login account from email, username, or legacy parent/student email."""
    from django.contrib.auth import get_user_model

    ident = (identifier or "").strip()
    if not ident:
        return None

    User = get_user_model()
    user = User.objects.filter(email__iexact=ident).first()
    if user:
        return user
    user = User.objects.filter(username__iexact=ident).first()
    if user:
        return user

    if "@" not in ident:
        return None

    from franchises.models import ParentProfile
    from students.models import StudentProfile

    pp = ParentProfile.objects.filter(Emailid__iexact=ident).select_related("user").first()
    if pp and pp.user_id:
        return pp.user

    sp = (
        StudentProfile.objects.filter(Emailid__iexact=ident)
        .select_related("parent__user")
        .first()
    )
    if sp and sp.parent_id and sp.parent.user_id:
        return sp.parent.user

    return None


def _resolve_recipient(user, to_email: str | None = None) -> str:
    return personal_email_for_user(user, preferred=to_email)


def send_registration_emails(
    user,
    *,
    to_email: str,
    full_name: str,
    franchise=None,
) -> tuple[str, bool]:
    """
    Register form (``/api/auth/register/``):
    - **Personal:** landing-style thank-you → typed email
    - **Personal:** password-set link → same inbox (never team inbox)
    """
    centre_name, centre_phone, centre_email = centre_details_from_franchise(franchise)
    send_personal_thankyou(
        to_email=to_email,
        name=full_name,
        centre_name=centre_name,
        centre_phone=centre_phone,
        centre_email=centre_email,
    )
    return send_password_reset_email(user, to_email=to_email)


def send_password_reset_email(user, *, to_email: str | None = None) -> tuple[str, bool]:
    """
    Send password-reset link. Uses SendGrid API (same as enquiries/careers).
    Falls back to Django EMAIL_BACKEND when SENDGRID_API_KEY is not set.

    Returns (reset_url, sent_ok).
    """
    reset_url = build_password_reset_url(user)
    recipient = _resolve_recipient(user, to_email)
    if not recipient:
        logger.warning(
            "Password reset skipped: user id=%s has no email (to_email=%r)",
            getattr(user, "pk", None),
            to_email,
        )
        return reset_url, False

    from_email = default_from_email()
    safe_url = html.escape(reset_url)
    subject = "T.I.M.E. Kids — Password reset"
    plain = (
        "Hi,\n\n"
        "Use the link below to set or reset your password:\n\n"
        f"{reset_url}\n\n"
        "If you did not request this, you can ignore this email.\n"
    )
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 24px;">
            <p>Hi,</p>
            <p>Use the button below to set or reset your password for T.I.M.E. Kids:</p>
            <p style="margin: 24px 0;">
                <a href="{safe_url}" style="display: inline-block; padding: 12px 24px;
                    background: #ea580c; color: #fff !important; text-decoration: none;
                    border-radius: 8px; font-weight: bold;">Reset password</a>
            </p>
            <p style="font-size: 13px; color: #666;">Or copy this link into your browser:<br/>
                <a href="{safe_url}">{safe_url}</a>
            </p>
            <p style="font-size: 12px; color: #888;">If you did not request this, you can ignore this email.</p>
        </div>
    </body>
    </html>
    """

    if sendgrid_api_key():
        if send_sendgrid_message(
            to_emails=recipient,
            subject=subject,
            plain_text_content=plain,
            html_content=html_content,
            from_email=from_email,
        ):
            return reset_url, True
        return reset_url, False

    # Dev only: no SENDGRID_API_KEY — prints to console (does not deliver to inbox)
    try:
        from django.core.mail import send_mail

        send_mail(
            subject=subject,
            message=plain,
            from_email=from_email,
            recipient_list=[recipient],
            fail_silently=False,
        )
        logger.warning(
            "Password reset logged to EMAIL_BACKEND=%s (not real SendGrid). "
            "Add SENDGRID_API_KEY to .env — same key as landing pages.",
            getattr(settings, "EMAIL_BACKEND", "?"),
        )
        return reset_url, True
    except Exception:
        logger.exception(
            "Email failed for password reset (user id=%s, recipient=%s). Set SENDGRID_API_KEY in .env.",
            getattr(user, "pk", None),
            recipient,
        )
        return reset_url, False
