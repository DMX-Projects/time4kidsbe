"""
Point each Franchise.user at the centre login (FRANCHISE role) when legacy import
left user_id on HO/admin accounts.

Matches by:
  1. slug prefix (including multi-segment / last-segment, e.g. EBColony)
  2. compact franchise name (e.g. KaveriNagar ↔ "Kaveri Nagar")

Run: python manage.py link_franchise_centre_logins
     python manage.py link_franchise_centre_logins --dry-run
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import UserRole
from accounts.profile_access import (
    _compact_centre_key,
    _normalize_centre_login_key,
    _slug_prefix_keys,
    franchise_slug_login_key,
)
from franchises.models import Franchise

User = get_user_model()


def _norm_role(user) -> str:
    return str(getattr(user, "role", "") or "").strip().upper()


def _candidate_keys_for_franchise(franchise) -> list[str]:
    keys: list[str] = []

    def add(raw: str | None) -> None:
        for variant in (
            _normalize_centre_login_key(raw),
            _compact_centre_key(raw),
        ):
            if variant and variant not in keys:
                keys.append(variant)

    add(franchise_slug_login_key(franchise.slug))
    for key in _slug_prefix_keys(franchise.slug or ""):
        add(key)
    add(franchise.name)
    return keys


def _find_centre_login(franchise, franchise_role: str):
    """Return a unique FRANCHISE-role user for this centre, or None."""
    keys = _candidate_keys_for_franchise(franchise)
    if not keys:
        return None

    seen: set[int] = set()
    candidates = []
    for key in keys:
        for user in User.objects.filter(role__iexact=franchise_role, username__iexact=key):
            if user.pk not in seen:
                seen.add(user.pk)
                candidates.append(user)

    if not candidates:
        # Compact username compare (Tambaramwest ↔ tambaramwest, spaces stripped in name key)
        compact_keys = {_compact_centre_key(k) for k in keys if _compact_centre_key(k)}
        for user in User.objects.filter(role__iexact=franchise_role).only(
            "id", "username", "last_login"
        ):
            if _compact_centre_key(user.username) in compact_keys:
                if user.pk not in seen:
                    seen.add(user.pk)
                    candidates.append(user)

    if not candidates:
        return None

    # Prefer a user who does not already own a different franchise row.
    free = []
    for user in candidates:
        owned = Franchise.objects.filter(user_id=user.pk).exclude(pk=franchise.pk).exists()
        if not owned:
            free.append(user)
    pool = free or candidates

    if len(pool) > 1:
        pool.sort(
            key=lambda u: (u.last_login is not None, u.last_login or u.pk),
            reverse=True,
        )
    return pool[0], len(candidates) > 1


class Command(BaseCommand):
    help = "Link Franchise.user to centre login accounts (username matches slug/name)."

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

                found = _find_centre_login(franchise, franchise_role)
                if not found:
                    skipped += 1
                    continue

                centre_user, was_ambiguous = found
                if was_ambiguous:
                    ambiguous += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Franchise #{franchise.id} ({franchise.slug}): "
                            f"multiple users matched; using {centre_user.username!r}"
                        )
                    )

                if franchise.user_id == centre_user.pk:
                    skipped += 1
                    continue

                # OneToOne: clear any other franchise still pointing at this login.
                other = (
                    Franchise.objects.filter(user_id=centre_user.pk)
                    .exclude(pk=franchise.pk)
                    .first()
                )
                if other:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipping Franchise #{franchise.id} {franchise.name!r}: "
                            f"login {centre_user.username!r} already owns "
                            f"Franchise #{other.id} {other.name!r}"
                        )
                    )
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
