"""Create and sync franchise centre notifications from head office actions."""

from __future__ import annotations

from django.utils import timezone

from .models import Announcement, FranchiseNotification, SupportTicket
from .support_ticket_notify import ticket_status_label

FRANCHISE_PARENT_TICKETS_PATH = "/dashboard/franchise/parent-tickets/"
FRANCHISE_PARENT_PORTAL_NOTIFICATIONS_PATH = "/dashboard/franchise/parent-portal/?tab=notifications"


def create_announcement_centre_notification(announcement: Announcement, franchise) -> FranchiseNotification:
    """Record a head-office CMS notification for a franchise centre inbox."""
    title = (announcement.title or "").strip() or "Head office notification"
    body = (announcement.body or "").strip()
    return FranchiseNotification.objects.create(
        franchise=franchise,
        source=FranchiseNotification.Source.HEAD_OFFICE,
        source_id=announcement.id,
        title=title,
        body=body,
        action_path=FRANCHISE_PARENT_PORTAL_NOTIFICATIONS_PATH,
    )


def sync_announcement_centre_notifications(announcement: Announcement, franchises=None) -> int:
    """
    Ensure each targeted centre has an inbox row for this global announcement.
    Removes stale rows when targeting changes.
    """
    if not announcement.visible_to_centres:
        FranchiseNotification.objects.filter(
            source=FranchiseNotification.Source.HEAD_OFFICE,
            source_id=announcement.id,
        ).delete()
        return 0

    from common.cms_targeting import franchises_matching_announcement

    targets = franchises if franchises is not None else franchises_matching_announcement(
        announcement,
        admin_user=getattr(announcement, "ho_admin", None),
    )
    target_ids = {f.id for f in targets}
    FranchiseNotification.objects.filter(
        source=FranchiseNotification.Source.HEAD_OFFICE,
        source_id=announcement.id,
    ).exclude(franchise_id__in=target_ids).delete()

    created = 0
    for franchise in targets:
        row = FranchiseNotification.objects.filter(
            franchise=franchise,
            source=FranchiseNotification.Source.HEAD_OFFICE,
            source_id=announcement.id,
        ).first()
        title = (announcement.title or "").strip() or "Head office notification"
        body = (announcement.body or "").strip()
        if row:
            changed = False
            if row.title != title:
                row.title = title
                changed = True
            if row.body != body:
                row.body = body
                changed = True
            if changed:
                row.save(update_fields=["title", "body"])
            continue
        create_announcement_centre_notification(announcement, franchise)
        created += 1
    return created


def sync_announcement_centre_notifications_for_franchise(franchise) -> int:
    """Backfill centre inbox rows for global HO announcements visible to this franchise."""
    from common.cms_targeting import announcement_visible_to_franchise

    candidates = Announcement.objects.filter(
        franchise__isnull=True,
        is_active=True,
        visible_to_centres=True,
    ).only(
        "id",
        "franchise_id",
        "publish_scope",
        "target_states",
        "target_cities",
        "target_franchise_ids",
        "is_active",
        "visible_to_centres",
        "title",
        "body",
    )
    created = 0
    for announcement in candidates:
        if not announcement_visible_to_franchise(announcement, franchise):
            continue
        has_row = FranchiseNotification.objects.filter(
            franchise=franchise,
            source=FranchiseNotification.Source.HEAD_OFFICE,
            source_id=announcement.id,
        ).exists()
        if not has_row:
            create_announcement_centre_notification(announcement, franchise)
            created += 1
    return created


def create_support_ticket_ho_notification(ticket: SupportTicket, *, message: str) -> FranchiseNotification:
    """Record a head-office support ticket reminder for the centre inbox."""
    franchise = ticket.parent.franchise
    subject = (ticket.subject or "").strip() or "Support ticket"
    title = f"Head office: resolve support ticket — {subject}"
    body = (message or "").strip() or (
        f'Ticket "{subject}" is still {ticket_status_label(ticket.status)}. '
        "Please reply to the parent and update the status."
    )
    return FranchiseNotification.objects.create(
        franchise=franchise,
        source=FranchiseNotification.Source.SUPPORT_TICKET,
        source_id=ticket.id,
        title=title,
        body=body,
        action_path=FRANCHISE_PARENT_TICKETS_PATH,
    )


def sync_support_ticket_ho_notifications(franchise) -> int:
    """Backfill inbox rows for tickets that already have HO reminders."""
    tickets = (
        SupportTicket.objects.filter(
            parent__franchise=franchise,
            ho_reminded_at__isnull=False,
        )
        .exclude(status=SupportTicket.Status.RESOLVED)
        .exclude(ho_reminder_message="")
    )
    created = 0
    for ticket in tickets:
        has_row = FranchiseNotification.objects.filter(
            franchise=franchise,
            source=FranchiseNotification.Source.SUPPORT_TICKET,
            source_id=ticket.id,
        ).exists()
        if not has_row:
            create_support_ticket_ho_notification(ticket, message=ticket.ho_reminder_message)
            created += 1
    return created
