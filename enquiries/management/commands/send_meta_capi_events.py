"""Send TIME Kids CRM stage events to Meta Conversions API (Conversion Leads)."""

from django.core.management.base import BaseCommand, CommandError

from enquiries.meta_capi import (
    build_crm_event,
    event_name_for_status,
    meta_capi_dataset_id,
    meta_capi_is_configured,
    meta_leadgen_id_from_lead,
    send_crm_stage_event,
)
from enquiries.models import CrmLead


class Command(BaseCommand):
    help = (
        "Upload CRM lead-stage events to Meta Conversions API. "
        "Production sends on Instant Form import and every CRM status change."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--test",
            action="store_true",
            help="Send as a test event (requires --test-event-code or META_CAPI_TEST_EVENT_CODE).",
        )
        parser.add_argument(
            "--test-event-code",
            default="",
            help="Test event code from Events Manager → Test events.",
        )
        parser.add_argument(
            "--crm-id",
            type=int,
            default=0,
            help="Send the current CRM stage for this campaign_leads id.",
        )
        parser.add_argument(
            "--backfill",
            action="store_true",
            help="Send the current stage for Instant Form leads that already exist in CRM.",
        )
        parser.add_argument("--limit", type=int, default=50, help="Max leads for --backfill (default 50).")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print payload only; do not call Meta.",
        )

    def handle(self, *args, **options):
        from django.conf import settings

        test_code = (
            options.get("test_event_code") or getattr(settings, "META_CAPI_TEST_EVENT_CODE", "") or ""
        ).strip()
        if options["test"] and not test_code:
            raise CommandError(
                "Pass --test-event-code (Events Manager → Test events) or set META_CAPI_TEST_EVENT_CODE."
            )
        if not options["test"]:
            test_code = ""

        if not options["dry_run"] and not meta_capi_is_configured():
            raise CommandError("META_CAPI_ACCESS_TOKEN is not set. Create a dataset access token in Events Manager.")

        self.stdout.write(f"Dataset {meta_capi_dataset_id()}")

        crm_id = int(options.get("crm_id") or 0)
        if crm_id:
            lead = CrmLead.objects.filter(pk=crm_id).first()
            if not lead:
                raise CommandError(f"CRM lead {crm_id} not found.")
            self._send_one(lead, test_code=test_code, dry_run=options["dry_run"])
            return

        if options["backfill"]:
            qs = (
                CrmLead.objects.filter(raw_payload__meta_leadgen_id__isnull=False)
                .exclude(raw_payload__meta_leadgen_id="")
                .order_by("-id")[: max(1, int(options["limit"] or 50))]
            )
            sent = skipped = failed = 0
            for lead in qs:
                result = self._send_one(lead, test_code=test_code, dry_run=options["dry_run"], quiet=True)
                if result.get("skipped"):
                    skipped += 1
                elif result.get("ok") or options["dry_run"]:
                    sent += 1
                else:
                    failed += 1
            self.stdout.write(self.style.SUCCESS(f"Backfill done: sent={sent} skipped={skipped} failed={failed}"))
            return

        if options["test"]:
            raise CommandError("With --test, also pass --crm-id <id> of a Meta Instant Form lead (or --backfill).")

        raise CommandError("Pass --crm-id, --backfill, or --test --crm-id.")

    def _send_one(self, lead: CrmLead, *, test_code: str, dry_run: bool, quiet: bool = False) -> dict:
        event_name = event_name_for_status(lead.status)
        leadgen = meta_leadgen_id_from_lead(lead)
        if dry_run:
            event = build_crm_event(lead, event_name=event_name)
            payload = event or {}
            self.stdout.write(
                f"dry-run crm_id={lead.pk} leadgen_id={leadgen} event_name={event_name} payload={payload}"
            )
            return {"ok": True, "skipped": not event, "dry_run": True}

        result = send_crm_stage_event(lead, event_name=event_name, test_event_code=test_code)
        if not quiet:
            if result.get("ok"):
                self.stdout.write(
                    self.style.SUCCESS(
                        "Sent {event} for crm_id={pk} leadgen_id={lg} response={resp}".format(
                            event=result.get("event_name") or event_name,
                            pk=lead.pk,
                            lg=leadgen,
                            resp=result.get("response"),
                        )
                    )
                )
            elif result.get("skipped"):
                self.stdout.write(f"Skipped crm_id={lead.pk}: {result.get('reason')}")
            else:
                self.stderr.write(
                    self.style.ERROR(f"Failed crm_id={lead.pk}: {result.get('error')} {result.get('detail')}")
                )
        return result
