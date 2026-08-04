"""
Re-run territory auto-assign for CrmLead rows.

Use on live after deploying auto-assign fixes:

  python manage.py backfill_crm_auto_assign --dry-run
  python manage.py backfill_crm_auto_assign
  python manage.py backfill_crm_auto_assign --fix-wrong

Default: only fills leads with no assignee.
``--fix-wrong`` also reassigns when the current assignee does not cover the lead state.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from enquiries.crm_users import (
    crm_users_matching_geo,
    is_meta_instant_form_lead,
    resolve_notify_lead_kind,
    suggest_assignee_for_geo,
)
from enquiries.emails import lead_source_label_for_crm_lead
from enquiries.models import CrmLead


def _assignee_covers_lead(lead, user) -> bool:
    if user is None:
        return False
    ignore_city = is_meta_instant_form_lead(lead)
    city = None if ignore_city else ((lead.city or "").strip() or None)
    matches = crm_users_matching_geo(
        (lead.state or "").strip() or None,
        city,
        ignore_city=ignore_city,
    )
    return any(u.id == user.id for u in matches)


class Command(BaseCommand):
    help = "Backfill CrmLead.assigned_user from territory mapping (franchise/admission)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without writing.",
        )
        parser.add_argument(
            "--fix-wrong",
            action="store_true",
            help="Also reassign leads whose current assignee is outside lead state territory.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Max leads to process (0 = all).",
        )

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        fix_wrong = bool(options["fix_wrong"])
        limit = int(options["limit"] or 0)

        qs = CrmLead.objects.select_related("assigned_user").order_by("-id")
        if not fix_wrong:
            qs = qs.filter(assigned_user_id__isnull=True)
        if limit > 0:
            qs = qs[:limit]

        filled = 0
        fixed = 0
        skipped = 0

        for lead in qs:
            source = lead_source_label_for_crm_lead(lead)
            kind = resolve_notify_lead_kind(lead, source)
            ignore_city = is_meta_instant_form_lead(lead)
            city = (lead.city or "").strip() or None

            suggested = suggest_assignee_for_geo(
                (lead.state or "").strip() or None,
                city,
                pipeline=kind,
                ignore_city=ignore_city,
            )
            if not suggested:
                skipped += 1
                continue

            current = lead.assigned_user
            if current is None:
                action = "fill"
            elif fix_wrong and not _assignee_covers_lead(lead, current):
                if current.id == suggested.id:
                    skipped += 1
                    continue
                action = "fix"
            else:
                skipped += 1
                continue

            self.stdout.write(
                f"{action}: crm-{lead.id} state={lead.state!r} city={lead.city!r} "
                f"{getattr(current, 'full_name', None) or '—'} -> {suggested.full_name}"
            )
            if dry_run:
                if action == "fill":
                    filled += 1
                else:
                    fixed += 1
                continue

            lead.assigned_user = suggested
            lead.save(update_fields=["assigned_user"])
            if action == "fill":
                filled += 1
            else:
                fixed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. filled={filled} fixed={fixed} skipped={skipped} dry_run={dry_run}"
            )
        )
