"""
Point each Franchise.user at the centre login (FRANCHISE role) when legacy import
left user_id on HO/admin accounts.

Run: python manage.py link_franchise_centre_logins
     python manage.py link_franchise_centre_logins --dry-run
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import UserRole
from accounts.profile_access import franchise_slug_login_key
from franchises.models import Franchise

User = get_user_model()


def _norm_role(user) -> str:
    return str(getattr(user, "role", "") or "").strip().upper()


class Command(BaseCommand):
    help = "Link Franchise.user to centre login accounts (username matches slug prefix)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print planned changes without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        updated = 0
        skipped = 0
        ambiguous = 0

        franchise_role = UserRole.FRANCHISE.value

        with transaction.atomic():
            for franchise in Franchise.objects.select_related("user").iterator():
                linked = franchise.user
                if linked and _norm_role(linked) == franchise_role:
                    skipped += 1
                    continue

                key = franchise_slug_login_key(franchise.slug)
                if not key:
                    skipped += 1
                    continue

                candidates = list(
                    User.objects.filter(role__iexact=franchise_role, username__iexact=key)
                )
                if len(candidates) > 1:
                    ambiguous += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skip franchise #{franchise.id} ({franchise.slug}): "
                            f"{len(candidates)} users named {key!r}"
                        )
                    )
                    continue
                if len(candidates) == 0:
                    skipped += 1
                    continue

                centre_user = candidates[0]
                if franchise.user_id == centre_user.pk:
                    skipped += 1
                    continue

                self.stdout.write(
                    f"{'[dry-run] ' if dry_run else ''}Franchise #{franchise.id} {franchise.name!r}: "
                    f"user_id {franchise.user_id} -> {centre_user.pk} ({centre_user.username})"
                )
                if not dry_run:
                    franchise.user_id = centre_user.pk
                    franchise.save(update_fields=["user_id"])
                updated += 1

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. updated={updated} skipped={skipped} ambiguous={ambiguous} dry_run={dry_run}"
            )
        )
