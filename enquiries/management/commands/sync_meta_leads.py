from django.core.management.base import BaseCommand

from enquiries.meta_leads import sync_page_leads


class Command(BaseCommand):
    help = "Poll Meta Lead Ads forms and import new leads into CRM (auto-sync backup)."

    def add_arguments(self, parser):
        parser.add_argument("--per-form-limit", type=int, default=20)
        parser.add_argument("--max-forms", type=int, default=100)
        parser.add_argument(
            "--no-emails",
            action="store_true",
            help="Import and auto-assign leads without sending parent/team/assignee emails.",
        )

    def handle(self, *args, **options):
        summary = sync_page_leads(
            per_form_limit=options["per_form_limit"],
            max_forms=options["max_forms"],
            send_emails=not options["no_emails"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Meta sync complete: forms={forms} imported={imported} skipped={skipped} failed={failed} emails={emails}".format(
                    emails="off" if options["no_emails"] else "on",
                    **summary,
                )
            )
        )
