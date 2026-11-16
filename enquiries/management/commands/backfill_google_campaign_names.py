"""
Fill blank Google campaign names from the landing URL / stored form payload.

Google Ads auto-tagging sends gad_campaignid, not the campaign name. Leads saved
before the form captured that id have an empty Campaign column even when the
landing URL still has utm_campaign or gad_campaignid.

  python manage.py backfill_google_campaign_names --dry-run
  python manage.py backfill_google_campaign_names
  python manage.py backfill_google_campaign_names --since 2026-11-05
"""

from __future__ import annotations

from datetime import datetime

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from enquiries.crm_api import (
    _is_numeric_campaign_id,
    _is_page_campaign_slug,
    _tracking_text,
    is_google_ads_landing_url,
    resolve_campaign_name,
)
from enquiries.models import CrmLead, CrmLeadSource


class Command(BaseCommand):
    help = "Backfill Google Ads campaign names on CRM leads from stored URLs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--since",
            default="2026-11-05",
            help="Only leads created on or after this date (YYYY-MM-DD). Default: 2026-11-05.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print changes without saving.",
        )

    def handle(self, *args, **options):
        since = _parse_since(options["since"])
        dry_run = bool(options["dry_run"])
        google_q = (
            Q(source__in=[CrmLeadSource.JULY_LP, CrmLeadSource.LP_WB, CrmLeadSource.CAMPAIGN_GOOGLE])
            | Q(gclid__gt="")
            | Q(utm_source__iexact="google")
            | Q(landing_page_url__icontains="gclid=")
            | Q(landing_page_url__icontains="gad_campaignid=")
            | Q(landing_page_url__icontains="gbraid=")
            | Q(landing_page_url__icontains="wbraid=")
        )
        qs = CrmLead.objects.filter(google_q, created_at__gte=since).order_by("id")
        updated = 0
        scanned = 0
        for lead in qs.iterator():
            scanned += 1
            raw = lead.raw_payload if isinstance(lead.raw_payload, dict) else {}
            landing_url = (
                str(raw.get("landingPageUrl") or raw.get("landing_page_url") or "").strip()
                or (lead.landing_page_url or "")
            )
            if not (
                lead.source in (CrmLeadSource.JULY_LP, CrmLeadSource.LP_WB, CrmLeadSource.CAMPAIGN_GOOGLE)
                or (lead.gclid or "").strip()
                or (lead.utm_source or "").strip().lower() == "google"
                or is_google_ads_landing_url(landing_url)
            ):
                continue
            current = (lead.utm_campaign or "").strip()
            if current and not _is_page_campaign_slug(current) and not _is_numeric_campaign_id(current):
                continue
            resolved = resolve_campaign_name(current, raw, landing_url)
            resolved = _tracking_text(resolved)
            if not resolved or resolved == current:
                continue
            if _is_page_campaign_slug(resolved):
                continue
            updated += 1
            self.stdout.write(f"{lead.id}: {current or '—'} -> {resolved}")
            if not dry_run:
                lead.utm_campaign = resolved[:150]
                lead.save(update_fields=["utm_campaign", "updated_at"])
        label = "would update" if dry_run else "updated"
        self.stdout.write(self.style.SUCCESS(f"Scanned {scanned}, {label} {updated}."))


def _parse_since(raw: str):
    text = (raw or "").strip()
    parsed = parse_datetime(text) or parse_date(text)
    if parsed is None:
        raise ValueError(f"Invalid --since date: {raw}")
    if isinstance(parsed, datetime):
        when = parsed
    else:
        when = datetime(parsed.year, parsed.month, parsed.day)
    if timezone.is_naive(when):
        when = timezone.make_aware(when, timezone.get_current_timezone())
    return when
