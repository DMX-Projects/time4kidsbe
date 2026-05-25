"""Email parents when the centre posts a new announcement (SendGrid)."""

from __future__ import annotations

import html
import logging
from typing import TYPE_CHECKING

from django.conf import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

if TYPE_CHECKING:
    from students.models import Announcement

logger = logging.getLogger(__name__)


def notify_parents_new_announcement(announcement: Announcement) -> int:
    """
    Email each parent at this franchise (except those with notifications_muted).
    Returns number of successfully queued SendGrid sends (202).
    """
    from franchises.models import ParentProfile

    if not announcement.is_active:
        return 0

    api_key = getattr(settings, "SENDGRID_API_KEY", None) or ""
    if not api_key.strip():
        logger.warning("SENDGRID_API_KEY not set; skipping parent announcement emails")
        return 0

    parents = ParentProfile.objects.filter(
        franchise=announcement.franchise,
        notifications_muted=False,
    ).select_related("user")

    base_url = getattr(settings, "PUBLIC_SITE_URL", "http://localhost:3000").rstrip("/")
    notifications_url = f"{base_url}/dashboard/parent/notifications"
    from_email = getattr(settings, "MAIL_FROM_ADDRESS", None) or getattr(
        settings, "DEFAULT_FROM_EMAIL", "info@timekidspreschools.com"
    )
    franchise_name = announcement.franchise.name

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
        addr = (pp.user.email or "").strip()
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
    return sent


def notify_parents_new_announcement_by_id(announcement_id: int) -> None:
    """Load announcement and notify; safe to call from a background thread after commit."""
    from students.models import Announcement

    try:
        ann = Announcement.objects.select_related("franchise").get(pk=announcement_id)
    except Announcement.DoesNotExist:
        logger.warning("notify_parents_new_announcement_by_id: Announcement %s missing", announcement_id)
        return
    notify_parents_new_announcement(ann)
