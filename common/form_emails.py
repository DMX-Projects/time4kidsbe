"""
Unified form email design (landing + admission + register).

All outbound mail uses the same SendGrid account:
  - SENDGRID_API_KEY
  - SENDGRID_FROM_EMAIL or MAIL_FROM_ADDRESS (e.g. info@timekidspreschools.com)

Two recipient roles:
  1. **Personal inbox** — the email the parent typed on the form (thank-you, password reset).
  2. **Team inbox** — MAIL_TO_ADDRESS (+ franchise contacts) for internal alerts only.
"""

from __future__ import annotations

import html
import logging
from typing import Iterable

from django.conf import settings

from common.sendgrid_email import default_from_email, send_sendgrid_message, sendgrid_api_key

logger = logging.getLogger(__name__)

PARENT_THANKYOU_SUBJECT = "Thank You for Your Interest in Timekids Preschool"
ADMISSION_ENQUIRY_SUBJECT = "We received your admission enquiry — Timekids Preschool"
DEFAULT_TEAM_INBOX = "info@timekidspreschools.com"
DEFAULT_FRANCHISE_TEAM_INBOX = "franchise@timekidspreschools.com"


def team_inbox() -> str:
    """Admission, landing, contact — internal alerts."""
    return (getattr(settings, "MAIL_TO_ADDRESS", None) or DEFAULT_TEAM_INBOX).strip()


def franchise_team_inbox() -> str:
    """Franchise opportunity form — internal alerts."""
    return (
        getattr(settings, "MAIL_FRANCHISE_TO_ADDRESS", None) or DEFAULT_FRANCHISE_TEAM_INBOX
    ).strip()


def parent_thankyou_cc() -> list[str]:
    raw = getattr(settings, "MAIL_LANDING_CC", None) or DEFAULT_TEAM_INBOX
    return [e.strip() for e in str(raw).split(",") if e.strip()]


def normalize_personal_email(value: str | None) -> str:
    """Submitter's own inbox — never HQ/team addresses."""
    addr = (value or "").strip()
    if addr and "@" in addr:
        return addr
    return ""


def centre_details_from_franchise(franchise) -> tuple[str, str, str]:
    if not franchise:
        return "—", "—", "—"
    name = (getattr(franchise, "name", None) or "").strip() or "—"
    phone = (getattr(franchise, "contact_phone", None) or "").strip() or "—"
    email = (getattr(franchise, "contact_email", None) or "").strip() or "—"
    return name, phone, email


def build_parent_thankyou_html(
    *,
    name: str,
    centre_name: str = "—",
    centre_phone: str = "—",
    centre_email: str = "—",
) -> str:
    """Landing / contact / register thank-you — keep original copy (do not shorten)."""
    safe_name = html.escape((name or "").strip() or "there")
    return f"""Hi {safe_name},<br><br>
Thank you for your interest in Timekids Preschool. We&rsquo;re delighted to connect with you.<br><br>
Please find below the details of your nearest centre :<br>
Centre Name : {html.escape(centre_name)}<br>
Contact Number : {html.escape(centre_phone)}<br>
Email ID : {html.escape(centre_email)}<br><br>
Please note that admissions are currently in progress and seats are limited.<br>
We encourage you to book a centre visit at the earliest to secure your child&rsquo;s admission.<br><br>
Our team will reach out to you shortly to assist you with admissions, curriculum details, and scheduling a visit to the centre.<br><br>
In the meantime, please feel free to contact the centre directly for any immediate queries.<br><br>
We look forward to being a part of your child&rsquo;s early learning journey.<br><br>
Warm regards,<br>Team Timekids"""


def build_admission_enquiry_thankyou_html(
    *,
    name: str,
    centre_name: str = "—",
    centre_phone: str = "—",
    centre_email: str = "—",
) -> str:
    """Parent thank-you after ``/admission/`` or ADMISSION enquiry submit (not landing pages)."""
    safe_name = html.escape((name or "").strip() or "there")
    site = (getattr(settings, "PUBLIC_SITE_URL", None) or "https://www.timekidspreschools.in").rstrip("/")
    login_url = html.escape(f"{site}/login/parents/")
    return f"""Hi {safe_name},<br><br>
Thank you for submitting the <strong>Admission Enquiry Form</strong> on the Timekids Preschool website.<br><br>
We have received your enquiry and our admissions team will review it shortly.<br><br>
<strong>Centre details</strong><br>
Centre Name : {html.escape(centre_name)}<br>
Email ID : {html.escape(centre_email)}<br><br>
If you are an existing parent and need to sign in, visit <a href="{login_url}">{login_url}</a>.<br><br>
Warm regards,<br>Team Timekids"""


def send_personal_thankyou(
    *,
    to_email: str,
    name: str,
    centre_name: str = "—",
    centre_phone: str = "—",
    centre_email: str = "—",
) -> bool:
    """Thank-you to the parent's personal email (landing pages + register)."""
    personal = normalize_personal_email(to_email)
    if not personal:
        logger.warning("Personal thank-you skipped: no recipient email")
        return False
    if not sendgrid_api_key():
        logger.warning("SENDGRID_API_KEY not set; personal thank-you skipped")
        return False

    body = build_parent_thankyou_html(
        name=name,
        centre_name=centre_name,
        centre_phone=centre_phone,
        centre_email=centre_email,
    )
    return send_sendgrid_message(
        to_emails=personal,
        subject=PARENT_THANKYOU_SUBJECT,
        html_content=body,
        from_email=default_from_email(),
        cc=parent_thankyou_cc(),
    )


def send_admission_enquiry_thankyou(
    *,
    to_email: str,
    name: str,
    centre_name: str = "—",
    centre_phone: str = "—",
    centre_email: str = "—",
) -> bool:
    """Thank-you after website Admission Enquiry Form (``/api/enquiries/submit/`` ADMISSION)."""
    personal = normalize_personal_email(to_email)
    if not personal:
        logger.warning("Admission thank-you skipped: no recipient email")
        return False
    if not sendgrid_api_key():
        logger.warning("SENDGRID_API_KEY not set; admission thank-you skipped")
        return False

    body = build_admission_enquiry_thankyou_html(
        name=name,
        centre_name=centre_name,
        centre_phone=centre_phone,
        centre_email=centre_email,
    )
    return send_sendgrid_message(
        to_emails=personal,
        subject=ADMISSION_ENQUIRY_SUBJECT,
        html_content=body,
        from_email=default_from_email(),
        cc=parent_thankyou_cc(),
    )


def send_team_notification(
    *,
    subject: str,
    html_content: str,
    extra_recipients: Iterable[str] | None = None,
    team_inbox_address: str | None = None,
) -> bool:
    """Internal alert — never the parent's typed email as primary To."""
    inbox = (team_inbox_address or "").strip() or team_inbox()
    if not inbox:
        logger.warning("MAIL_TO_ADDRESS not set; team notification skipped")
        return False
    if not sendgrid_api_key():
        logger.warning("SENDGRID_API_KEY not set; team notification skipped")
        return False

    recipients = [inbox]
    if extra_recipients:
        for addr in extra_recipients:
            a = (addr or "").strip()
            if a and "@" in a and a not in recipients:
                recipients.append(a)

    return send_sendgrid_message(
        to_emails=recipients,
        subject=subject,
        html_content=html_content,
        from_email=default_from_email(),
    )


def send_form_email_pair(
    *,
    personal_email: str,
    parent_name: str,
    centre_name: str = "—",
    centre_phone: str = "—",
    centre_email: str = "—",
    team_subject: str,
    team_html: str,
    team_extra_recipients: Iterable[str] | None = None,
    personal_template: str = "landing",
) -> str:
    """
    Dual send: personal thank-you + team alert.

    ``personal_template``: ``landing`` (default) or ``admission`` (website enquiry form).

    Returns: ``sent`` | ``partial`` | ``failed`` | ``skipped``
    """
    if not sendgrid_api_key():
        return "skipped"

    kwargs = dict(
        to_email=personal_email,
        name=parent_name,
        centre_name=centre_name,
        centre_phone=centre_phone,
        centre_email=centre_email,
    )
    if personal_template == "admission":
        parent_ok = send_admission_enquiry_thankyou(**kwargs)
    else:
        parent_ok = send_personal_thankyou(**kwargs)
    team_ok = send_team_notification(
        subject=team_subject,
        html_content=team_html,
        extra_recipients=team_extra_recipients,
    )
    if parent_ok and team_ok:
        return "sent"
    if parent_ok or team_ok:
        return "partial"
    return "failed"
