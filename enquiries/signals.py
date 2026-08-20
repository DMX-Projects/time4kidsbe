"""Enquiry / campaign-lead signal handlers."""

from __future__ import annotations

import logging

from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver

from .models import CrmLead

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=CrmLead)
def capture_crm_status_before_save(sender, instance: CrmLead, **kwargs) -> None:
    """Remember previous status so CAPI only fires on real stage changes."""
    if not instance.pk:
        instance._meta_capi_prev_status = None  # type: ignore[attr-defined]
        return
    try:
        instance._meta_capi_prev_status = sender.objects.filter(pk=instance.pk).values_list(  # type: ignore[attr-defined]
            "status", flat=True
        ).first()
    except Exception:
        instance._meta_capi_prev_status = None  # type: ignore[attr-defined]


@receiver(post_save, sender=CrmLead)
def send_meta_capi_on_crm_stage_change(sender, instance: CrmLead, created: bool, raw: bool = False, **kwargs) -> None:
    """Upload Conversion Leads events: Lead on Instant Form import, then every CRM stage."""
    if raw:
        return
    try:
        from .meta_capi import (
            event_name_for_status,
            is_qualified_capi_status,
            meta_leadgen_id_from_lead,
            schedule_crm_stage_event,
        )

        if not meta_leadgen_id_from_lead(instance):
            return
        if created:
            # New Instant Form rows start as Untouched — not a qualified event.
            if not is_qualified_capi_status(instance.status):
                return
            schedule_crm_stage_event(instance, event_name=event_name_for_status(instance.status))
            return
        prev = getattr(instance, "_meta_capi_prev_status", None)
        if prev is None or prev == instance.status:
            return
        schedule_crm_stage_event(instance, event_name=event_name_for_status(instance.status))
    except Exception:
        logger.exception(
            "Failed to schedule Meta CAPI event for CRM lead id=%s",
            getattr(instance, "pk", None),
        )


@receiver(pre_delete, sender=CrmLead)
def suppress_meta_lead_on_crm_delete(sender, instance: CrmLead, **kwargs) -> None:
    """Deleting a Meta Instant Form lead in CRM must not allow auto-sync to restore it."""
    try:
        from .meta_leads import suppress_meta_lead_from_crm_lead

        suppress_meta_lead_from_crm_lead(instance)
    except Exception:
        logger.exception(
            "Failed to suppress Meta leadgen on CRM delete id=%s",
            getattr(instance, "pk", None),
        )
