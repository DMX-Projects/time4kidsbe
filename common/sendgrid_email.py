"""
Shared SendGrid delivery for landing pages, enquiries, password reset, careers, etc.

Set ``SENDGRID_API_KEY`` once in ``.env`` (same key as landing pages).
"""

from __future__ import annotations

import logging
from typing import Iterable

from django.conf import settings

logger = logging.getLogger(__name__)


def sendgrid_api_key() -> str:
    return (getattr(settings, "SENDGRID_API_KEY", None) or "").strip()


def default_from_email() -> str:
    return (
        getattr(settings, "MAIL_FROM_ADDRESS", None)
        or getattr(settings, "DEFAULT_FROM_EMAIL", None)
        or "info@timekidspreschools.com"
    )


def send_sendgrid_message(
    *,
    to_emails: str | Iterable[str],
    subject: str,
    html_content: str = "",
    plain_text_content: str = "",
    from_email: str | None = None,
    cc: Iterable[str] | None = None,
) -> bool:
    """
    Send via SendGrid HTTP API (same as landing enquiry emails).

    Returns True when SendGrid accepts the message (HTTP 200/201/202).
    """
    api_key = sendgrid_api_key()
    if not api_key:
        logger.warning("SENDGRID_API_KEY not set; email not sent (subject=%r)", subject)
        return False

    if isinstance(to_emails, str):
        recipients = [to_emails]
    else:
        recipients = [e for e in to_emails if e]

    if not recipients:
        logger.warning("No recipients for SendGrid send (subject=%r)", subject)
        return False

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Cc, Mail

        kwargs: dict = {
            "from_email": from_email or default_from_email(),
            "to_emails": recipients,
            "subject": subject,
        }
        if plain_text_content:
            kwargs["plain_text_content"] = plain_text_content
        if html_content:
            kwargs["html_content"] = html_content
        message = Mail(**kwargs)
        if cc:
            for addr in cc:
                if addr and addr not in recipients:
                    message.add_cc(Cc(addr))

        response = SendGridAPIClient(api_key).send(message)
        if response.status_code in (200, 201, 202):
            logger.info("SendGrid sent %r to %s", subject, recipients)
            return True
        logger.error("SendGrid failed %r: HTTP %s body=%s", subject, response.status_code, response.body)
        return False
    except Exception:
        logger.exception("SendGrid failed for subject=%r to=%s", subject, recipients)
        return False
