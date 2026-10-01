"""
Move every lead assigned to one CRM user onto another, optionally deactivating the old login.

  python manage.py handover_crm_user_leads --from sujee@timekidspreschools.com \
      --to jyoti.mishra@timekidspreschools.com --deactivate --dry-run
  python manage.py handover_crm_user_leads --from sujee@timekidspreschools.com \
      --to jyoti.mishra@timekidspreschools.com --deactivate

Only ``assigned_user`` changes — status, notes, meetings and follow-ups stay on each lead.
Bulk update skips save signals, so no new-lead emails are re-sent.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from enquiries.models import CrmLead, Enquiry, FranchiseEnquiry, KidsEnquiry

LEAD_MODELS = (CrmLead, Enquiry, FranchiseEnquiry, KidsEnquiry)


class Command(BaseCommand):
    help = "Reassign all leads from one CRM user to another (optionally deactivate the old user)."

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="from_email", required=True, help="Current assignee email")
        parser.add_argument("--to", dest="to_email", required=True, help="New assignee email")
        parser.add_argument(
            "--deactivate",
            action="store_true",
            help="Deactivate the --from user after the handover",
        )
        parser.add_argument("--dry-run", action="store_true", help="Show counts without writing")

    def handle(self, *args, **options):
        from_email = options["from_email"].strip().lower()
        to_email = options["to_email"].strip().lower()
        dry_run = bool(options["dry_run"])

        source = User.objects.filter(email__iexact=from_email).first()
        if not source:
            raise CommandError(f"User not found: {from_email}")
        target = User.objects.filter(email__iexact=to_email, is_active=True).first()
        if not target:
            raise CommandError(f"Active user not found: {to_email}")
        if source.pk == target.pk:
            raise CommandError("--from and --to are the same user")

        total = 0
        with transaction.atomic():
            for model in LEAD_MODELS:
                qs = model.objects.filter(assigned_user_id=source.pk)
                count = qs.count()
                total += count
                if count and not dry_run:
                    qs.update(assigned_user_id=target.pk)
                self.stdout.write(f"{model.__name__}: {count} lead(s)")

            if options["deactivate"] and source.is_active and not dry_run:
                source.is_active = False
                source.save(update_fields=["is_active"])

        verb = "Would move" if dry_run else "Moved"
        self.stdout.write(
            self.style.SUCCESS(f"{verb} {total} lead(s) {source.email} -> {target.email}")
        )
        if options["deactivate"]:
            state = "would be deactivated" if dry_run else "deactivated"
            self.stdout.write(self.style.WARNING(f"{source.email} {state}"))
