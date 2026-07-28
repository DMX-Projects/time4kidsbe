"""
Block existing Meta Instant Form leads from (re)entering CRM.

Use after deleting campaign_leads rows so auto-sync cannot restore them.
Only brand-new Meta leadgen IDs (created after this) will sync.

  python manage.py suppress_existing_meta_leads
  python manage.py suppress_existing_meta_leads --also-crm
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from enquiries.meta_leads import (
    is_allowed_meta_form,
    meta_page_id,
    suppress_meta_leadgen,
    _graph_get,
)
from enquiries.models import CrmLead, MetaLeadSuppress


class Command(BaseCommand):
    help = (
        "Suppress all current Instant Form leads on the 48 BCWW TK forms "
        "(and optionally every Meta leadgen already in CRM) so deleted rows "
        "cannot be re-synced. New form fills still import."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--also-crm",
            action="store_true",
            help="Also suppress every meta_leadgen_id already stored on campaign_leads.",
        )
        parser.add_argument(
            "--per-form-limit",
            type=int,
            default=100,
            help="Max leads to read per Instant Form (default 100).",
        )

    def handle(self, *args, **options):
        also_crm = bool(options["also_crm"])
        per_form_limit = max(1, min(int(options["per_form_limit"] or 100), 200))
        page_id = meta_page_id()

        forms: list[dict] = []
        after = None
        while True:
            params = {"fields": "id,name", "limit": "100"}
            if after:
                params["after"] = after
            payload = _graph_get(f"{page_id}/leadgen_forms", params)
            batch = payload.get("data") or []
            forms.extend(batch)
            after = ((payload.get("paging") or {}).get("cursors") or {}).get("after")
            if not after or not batch:
                break

        campaign_forms = [
            f
            for f in forms
            if is_allowed_meta_form(
                form_id=str(f.get("id") or ""),
                form_name=str(f.get("name") or "").strip(),
            )
        ]
        self.stdout.write(f"Campaign Instant Forms: {len(campaign_forms)}")

        added = 0
        seen = 0
        for form in campaign_forms:
            form_id = str(form.get("id") or "").strip()
            form_name = str(form.get("name") or "").strip()
            if not form_id:
                continue
            after = None
            fetched = 0
            while fetched < per_form_limit:
                params = {
                    "fields": "id,created_time",
                    "limit": str(min(50, per_form_limit - fetched)),
                }
                if after:
                    params["after"] = after
                try:
                    leads_payload = _graph_get(f"{form_id}/leads", params)
                except Exception as exc:
                    self.stderr.write(f"Form leads failed {form_name}: {exc}")
                    break
                batch = leads_payload.get("data") or []
                if not batch:
                    break
                for lead in batch:
                    leadgen_id = str(lead.get("id") or "").strip()
                    if not leadgen_id:
                        continue
                    seen += 1
                    before = MetaLeadSuppress.objects.filter(leadgen_id=leadgen_id).exists()
                    suppress_meta_leadgen(
                        leadgen_id,
                        form_id=form_id,
                        form_name=form_name,
                    )
                    if not before:
                        added += 1
                fetched += len(batch)
                after = ((leads_payload.get("paging") or {}).get("cursors") or {}).get("after")
                if not after:
                    break

        crm_added = 0
        if also_crm:
            for lead in CrmLead.objects.iterator():
                payload = lead.raw_payload if isinstance(lead.raw_payload, dict) else {}
                leadgen_id = str(payload.get("meta_leadgen_id") or "").strip()
                if not leadgen_id:
                    continue
                before = MetaLeadSuppress.objects.filter(leadgen_id=leadgen_id).exists()
                suppress_meta_leadgen(
                    leadgen_id,
                    form_id=str(payload.get("meta_form_id") or ""),
                    form_name=str(payload.get("meta_form_name") or ""),
                    crm_lead_id=lead.pk,
                )
                if not before:
                    crm_added += 1

        total = MetaLeadSuppress.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Meta leads scanned={seen}, newly suppressed={added}, "
                f"from CRM={crm_added}, suppress table total={total}."
            )
        )
        self.stdout.write(
            "Deleted Instant Form leads will not re-sync. "
            "Only NEW Meta submissions (new leadgen IDs) will enter CRM."
        )
        self.stdout.write(
            "Optional: set META_LEADS_SYNC_SINCE to today's ISO datetime "
            "(UTC) for an extra cutoff, then restart the app."
        )
