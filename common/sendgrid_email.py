"""
Shared SendGrid delivery for landing pages, enquiries, password reset, careers, etc.

Set ``SENDGRID_API_KEY`` once in ``.env`` (same key as landing pages).
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Iterable, Sequence

from django.conf import settings

logger = logging.getLogger(__name__)

# (file_bytes, filename, mime_type) — mime defaults to application/pdf when omitted downstream
AttachmentPayload = tuple[bytes, str] | tuple[bytes, str, str]


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
    attachments: Sequence[AttachmentPayload] | None = None,
) -> bool:
    """
    Send via SendGrid HTTP API (same as landing enquiry emails).

    Optional ``attachments``: sequence of (bytes, filename) or (bytes, filename, mime).

    Returns True when SendGrid accepts the message (HTTP 200/201/202).
    """
    if not bool(getattr(settings, "EMAIL_SENDING_ENABLED", False)):
        logger.info(
            "Email sending disabled (EMAIL_SENDING_ENABLED=False); skipped subject=%r",
            subject,
        )
        return False

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
        from sendgrid.helpers.mail import (
            Attachment,
            Cc,
            Disposition,
            FileContent,
            FileName,
            FileType,
            Mail,
        )

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

        for item in attachments or ():
            raw = item[0]
            filename = item[1] or "attachment.pdf"
            mime = item[2] if len(item) > 2 else "application/pdf"
            if not raw:
                continue
            encoded = base64.b64encode(raw).decode()
            message.add_attachment(
                Attachment(
                    FileContent(encoded),
                    FileName(filename),
                    FileType(mime),
                    Disposition("attachment"),
                )
            )

        response = SendGridAPIClient(api_key).send(message)
        if response.status_code in (200, 201, 202):
            logger.info("SendGrid sent %r to %s", subject, recipients)
            return True
        logger.error("SendGrid failed %r: HTTP %s body=%s", subject, response.status_code, response.body)
        return False
    except Exception:
        logger.exception("SendGrid failed for subject=%r to=%s", subject, recipients)
        return False


def load_franchise_brochure_attachment() -> AttachmentPayload | None:
    """
    Load the franchise brochure PDF for personal thank-you emails.

    Prefers MarketingAsset slug ``franchise-brochure``; falls back to known
    filenames under MEDIA_ROOT/assets/.
    """
    try:
        from common.models import MarketingAsset

        asset = (
            MarketingAsset.objects.filter(slug="franchise-brochure", is_active=True)
            .exclude(file="")
            .first()
        )
        if asset and asset.file:
            try:
                with asset.file.open("rb") as fh:
                    data = fh.read()
                if data:
                    name = Path(asset.file.name).name or "franchise-brochure.pdf"
                    return data, name, "application/pdf"
            except Exception:
                logger.exception("Could not read MarketingAsset franchise-brochure file")
    except Exception:
        logger.exception("Could not load MarketingAsset franchise-brochure")

    media_root = Path(getattr(settings, "MEDIA_ROOT", "") or "")
    assets_dir = media_root / "assets"
    candidates = [
        assets_dir / "franchise-brochure.pdf",
        assets_dir / "6_Page_brochure_Frenchise_Brochure_for_Website.pdf",
    ]
    for path in candidates:
        try:
            if path.is_file():
                data = path.read_bytes()
                if data:
                    return data, "franchise-brochure.pdf", "application/pdf"
        except Exception:
            logger.exception("Could not read brochure fallback %s", path)
    logger.warning("Franchise brochure PDF not found for email attachment")
    return None
