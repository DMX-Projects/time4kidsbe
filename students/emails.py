"""Email parents when the centre posts a new announcement (SendGrid)."""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

if TYPE_CHECKING:
    from students.models import Announcement

logger = logging.getLogger(__name__)


def _parent_notification_email(parent_profile) -> str:
    """Best deliverable email for a parent (user login email, then profile/student Emailid)."""
    user_email = (getattr(getattr(parent_profile, "user", None), "email", None) or "").strip()
    profile_email = (getattr(parent_profile, "Emailid", None) or "").strip()
    if profile_email and "@" in profile_email:
        if not user_email or user_email.lower().endswith("@time4kids.local"):
            return profile_email
    if user_email and "@" in user_email:
        return user_email
    return profile_email if profile_email and "@" in profile_email else ""


def notify_parents_new_announcement(announcement: Announcement) -> int:
    """
    Email each parent at this franchise (except those with notifications_muted).
    Returns number of successfully queued SendGrid sends (202).
    """
    from students.portal_views import parent_profiles_for_announcement

    if not announcement.is_active:
        return 0

    if not getattr(announcement, "visible_to_parents", True):
        return 0

    if announcement.email_dispatched_at:
        return 0

    if announcement.published_at and announcement.published_at > timezone.now():
        return 0

    api_key = getattr(settings, "SENDGRID_API_KEY", None) or ""
    if not api_key.strip():
        logger.warning("SENDGRID_API_KEY not set; skipping parent announcement emails")
        return 0

    parents = parent_profiles_for_announcement(announcement).filter(notifications_muted=False)

    base_url = getattr(settings, "PUBLIC_SITE_URL", "http://localhost:3000").rstrip("/")
    notifications_url = f"{base_url}/dashboard/parent/notifications"
    from_email = getattr(settings, "MAIL_FROM_ADDRESS", None) or getattr(
        settings, "DEFAULT_FROM_EMAIL", "info@timekidspreschools.com"
    )
    franchise_name = (
        announcement.franchise.name
        if announcement.franchise_id
        else "TIME4Kids Head Office"
    )

    safe_franchise = html.escape(franchise_name)
    safe_title = html.escape(announcement.title)
    body_text = announcement.body or ""
    safe_body = html.escape(body_text).replace("\n", "<br/>")

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 24px; }}
            .btn {{ display: inline-block; margin-top: 16px; padding: 12px 20px;
 background: #ea580c; color: #fff !important; text-decoration: none;
                    border-radius: 8px; font-weight: bold; }}
            .footer {{ margin-top: 24px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <p><strong>{safe_franchise}</strong> has posted a new announcement for parents.</p>
            <h2 style="color:#1e3a5f;margin:16px 0 8px;">{safe_title}</h2>
            <div>{safe_body}</div>
            <a class="btn" href="{html.escape(notifications_url)}">Open parent dashboard — Notifications</a>
            <p class="footer">You can also sign in to the Parent App and open the Notifications section.</p>
        </div>
    </body>
    </html>
    """

    sent = 0
    seen: set[str] = set()
    sg = SendGridAPIClient(api_key)

    for pp in parents:
        addr = _parent_notification_email(pp)
        if not addr or addr.lower() in seen:
            continue
        seen.add(addr.lower())
        subject = f"{franchise_name}: {announcement.title}"
        try:
            message = Mail(
                from_email=from_email,
                to_emails=addr,
                subject=subject,
                html_content=html_content,
            )
            response = sg.send(message)
            if response.status_code == 202:
                sent += 1
            else:
                logger.warning(
                    "SendGrid status %s sending announcement to %s",
                    response.status_code,
                    addr,
                )
        except Exception:
            logger.exception("Failed to send announcement email to %s", addr)

    logger.info(
        "Announcement id=%s: emailed %s parent(s) (franchise=%s)",
        announcement.pk,
        sent,
        franchise_name,
    )

    parent_count = parents.count()
    if sent > 0 or parent_count == 0:
        from students.models import Announcement

        Announcement.objects.filter(pk=announcement.pk, email_dispatched_at__isnull=True).update(
            email_dispatched_at=timezone.now()
        )

    return sent


def dispatch_due_announcement_emails() -> int:
    """Send emails for scheduled announcements whose publish time has arrived."""
    from students.models import Announcement

    due = Announcement.objects.filter(
        is_active=True,
        visible_to_parents=True,
        email_dispatched_at__isnull=True,
        published_at__lte=timezone.now(),
    ).select_related("franchise", "student", "student__parent")

    total = 0
    for announcement in due:
        total += notify_parents_new_announcement(announcement)
    return total


def notify_parents_new_announcement_by_id(announcement_id: int) -> None:
    """Load announcement and notify; safe to call from a background thread after commit."""
    from students.models import Announcement

    try:
        ann = Announcement.objects.select_related("franchise", "student", "student__parent").get(pk=announcement_id)
    except Announcement.DoesNotExist:
        logger.warning("notify_parents_new_announcement_by_id: Announcement %s missing", announcement_id)
        return
    notify_parents_new_announcement(ann)


def notify_franchise_unresolved_ticket(ticket, *, message: str) -> bool:
    """Email the centre login when head office reminds them about an open ticket."""
    from students.models import SupportTicket

    if ticket.status == SupportTicket.Status.RESOLVED:
        return False

    try:
        franchise = ticket.parent.franchise
        centre_user = franchise.user
    except Exception:
        logger.warning("notify_franchise_unresolved_ticket: missing franchise for ticket %s", ticket.pk)
        return False

    addr = (getattr(centre_user, "email", None) or "").strip()
    if not addr or "@" not in addr:
        logger.warning("notify_franchise_unresolved_ticket: no email for franchise %s", franchise.pk)
        return False

    api_key = getattr(settings, "SENDGRID_API_KEY", None) or ""
    if not api_key.strip():
        logger.warning("SENDGRID_API_KEY not set; skipping franchise ticket reminder email")
        return False

    base_url = getattr(settings, "PUBLIC_SITE_URL", "http://localhost:3000").rstrip("/")
    tickets_url = f"{base_url}/dashboard/franchise/parent-tickets/"
    from_email = getattr(settings, "MAIL_FROM_ADDRESS", None) or getattr(
        settings, "DEFAULT_FROM_EMAIL", "info@timekidspreschools.com"
    )

    safe_centre = html.escape(franchise.name)
    safe_subject = html.escape(ticket.subject)
    safe_message = html.escape(message).replace("\n", "<br/>")
    safe_parent = html.escape(
        getattr(ticket.parent, "child_name", None) or str(ticket.parent)
    )
    status_label = html.escape(ticket.get_status_display())

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:Arial,sans-serif;line-height:1.6;color:#333;">
        <div style="max-width:600px;margin:0 auto;padding:24px;">
            <p><strong>Head office</strong> has asked your centre to action a parent support ticket.</p>
            <p><strong>Centre:</strong> {safe_centre}</p>
            <p><strong>Parent:</strong> {safe_parent}</p>
            <p><strong>Ticket:</strong> {safe_subject}</p>
            <p><strong>Status:</strong> {status_label}</p>
            <p>{safe_message}</p>
            <a href="{html.escape(tickets_url)}"
               style="display:inline-block;margin-top:16px;padding:12px 20px;background:#ea580c;color:#fff;
                      text-decoration:none;border-radius:8px;font-weight:bold;">
                Open Parent Support tickets
            </a>
        </div>
    </body>
    </html>
    """

    subject = f"Action required: parent support ticket — {ticket.subject}"
    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(
            Mail(
                from_email=from_email,
                to_emails=addr,
                subject=subject,
                html_content=html_content,
            )
        )
        if response.status_code == 202:
            logger.info("Ticket reminder emailed to %s (ticket=%s)", addr, ticket.pk)
            return True
        logger.warning("SendGrid status %s for ticket reminder to %s", response.status_code, addr)
    except Exception:
        logger.exception("Failed to send ticket reminder to %s", addr)
    return False
