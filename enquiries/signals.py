"""Enquiry / campaign-lead signal handlers."""

from __future__ import annotations

import logging

from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import CrmLead

logger = logging.getLogger(__name__)


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
