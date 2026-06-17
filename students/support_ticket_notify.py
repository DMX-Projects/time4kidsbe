"""Parent notifications and FCM push when franchise staff update support tickets."""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request

from django.conf import settings

from .models import ParentPushDevice, SupportTicket, SupportTicketStatusEvent

logger = logging.getLogger(__name__)

STATUS_LABELS = {
    SupportTicket.Status.OPEN: "Open",
    SupportTicket.Status.IN_PROGRESS: "In progress",
    SupportTicket.Status.RESOLVED: "Resolved",
    "CLOSED": "Resolved",
}


def ticket_status_label(status: str) -> str:
    if not status:
        return "Updated"
    return STATUS_LABELS.get(status, status.replace("_", " ").title())


def record_ticket_update_for_parent(
    ticket: SupportTicket,
    *,
    old_status: str,
    status_changed: bool,
    reply_changed: bool,
) -> SupportTicketStatusEvent | None:
    """Create an in-app notification event; push on status change only."""
    if status_changed:
        message = (
            f'Your support ticket "{ticket.subject}" is now {ticket_status_label(ticket.status)}.'
        )
        event = SupportTicketStatusEvent.objects.create(
            ticket=ticket,
            event_type=SupportTicketStatusEvent.EventType.STATUS_CHANGE,
            old_status=old_status,
            new_status=ticket.status,
            message=message,
        )
        _send_push_async(
            ticket,
            title="Support ticket updated",
            body=message,
            data={
                "type": "support_ticket",
                "ticket_id": ticket.id,
                "event_id": event.id,
                "status": ticket.status,
            },
        )
        return event

    if reply_changed and (ticket.franchise_reply or "").strip():
        message = f'Your centre replied to "{ticket.subject}".'
        return SupportTicketStatusEvent.objects.create(
            ticket=ticket,
            event_type=SupportTicketStatusEvent.EventType.REPLY,
            old_status=old_status,
            new_status=ticket.status,
            message=message,
        )

    return None


def _send_push_async(ticket: SupportTicket, *, title: str, body: str, data: dict) -> None:
    thread = threading.Thread(
        target=_send_push_to_parent,
        args=(ticket.parent_id, title, body, data),
        daemon=True,
    )
    thread.start()


def _send_push_to_parent(parent_id: int, title: str, body: str, data: dict | None = None) -> None:
    server_key = (getattr(settings, "FCM_SERVER_KEY", None) or "").strip()
    if not server_key:
        return

    tokens = list(
        ParentPushDevice.objects.filter(parent_id=parent_id).values_list("token", flat=True)
    )
    if not tokens:
        return

    payload = {
        "registration_ids": tokens,
        "notification": {"title": title, "body": body},
        "data": {k: str(v) for k, v in (data or {}).items()},
        "priority": "high",
    }
    req = urllib.request.Request(
        "https://fcm.googleapis.com/fcm/send",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"key={server_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status >= 400:
                logger.warning("FCM push failed for parent %s: HTTP %s", parent_id, resp.status)
    except urllib.error.URLError as exc:
        logger.warning("FCM push error for parent %s: %s", parent_id, exc)
