"""
Link one centre login user to a franchise row (fixes empty parent/student lists).

  python manage.py link_centre_login Vennala_New --franchise-name Vennala
  python manage.py link_centre_login Vennala_New --franchise-id 528
  python manage.py link_centre_login Vennala_New --franchise-slug vennala --dry-run
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import UserRole
from accounts.profile_access import franchise_centre_diagnostics, franchise_profile_for_user
from franchises.models import Franchise

User = get_user_model()


class Command(BaseCommand):
    help = "Link a centre login (FRANCHISE user) to a franchise row."

    def add_arguments(self, parser):
        parser.add_argument("username", help="Centre login username, e.g. Vennala_New")
        parser.add_argument("--franchise-id", type=int, default=0, help="Target franchise id")
        parser.add_argument("--franchise-name", default="", help="Target franchise name (exact, case-insensitive)")
        parser.add_argument("--franchise-slug", default="", help="Match franchise slug containing this text")
        parser.add_argument("--dry-run", action="store_true", help="Preview without saving")

    def handle(self, *args, **options):
        username = (options["username"] or "").strip()
        dry_run = bool(options.get("dry_run"))

        user = User.objects.filter(username__iexact=username).first()
        if not user:
            self.stderr.write(self.style.ERROR(f"No user with username {username!r}"))
            return

        role = str(getattr(user, "role", "") or "").strip().upper()
        if role != UserRole.FRANCHISE.value:
            self.stderr.write(
                self.style.ERROR(f"User {username!r} has role {role!r}; expected FRANCHISE.")
            )
            return

        franchise = self._resolve_franchise(options)
        if not franchise:
            return

        before = franchise_centre_diagnostics(user)
        self.stdout.write(
            f"User: {user.username} (id={user.pk})\n"
            f"Franchise: {franchise.name!r} (id={franchise.id}, slug={franchise.slug})\n"
            f"Current franchise.user_id: {franchise.user_id}\n"
            f"Before link — students={before['students_count']} parents={before['parents_count']} "
            f"resolve={before.get('resolve_method')}"
        )

        if franchise.user_id == user.pk:
            self.stdout.write(self.style.SUCCESS("Already linked to this user."))
            return

        label = "[dry-run] " if dry_run else ""
        self.stdout.write(
            f"{label}Set franchise #{franchise.id} user_id {franchise.user_id} -> {user.pk} ({user.username})"
        )

        if not dry_run:
            with transaction.atomic():
                franchise.user_id = user.pk
                franchise.save(update_fields=["user_id"])

        after = franchise_centre_diagnostics(user)
        resolved = franchise_profile_for_user(user)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Franchise resolved={resolved.name if resolved else None!r} "
                f"students={after['students_count']} parents={after['parents_count']}"
            )
        )

    def _resolve_franchise(self, options):
        franchise_id = int(options.get("franchise_id") or 0)
        name = (options.get("franchise_name") or "").strip()
        slug_q = (options.get("franchise_slug") or "").strip()

        if franchise_id:
            franchise = Franchise.objects.filter(pk=franchise_id).first()
            if not franchise:
                self.stderr.write(self.style.ERROR(f"No franchise with id={franchise_id}"))
            return franchise

        if name:
            franchise = Franchise.objects.filter(name__iexact=name).order_by("id").first()
            if not franchise:
                self.stderr.write(self.style.ERROR(f"No franchise named {name!r}"))
            return franchise

        if slug_q:
            matches = list(Franchise.objects.filter(slug__icontains=slug_q).order_by("id"))
            if not matches:
                self.stderr.write(self.style.ERROR(f"No franchise slug contains {slug_q!r}"))
                return None
            if len(matches) > 1:
                self.stderr.write(self.style.ERROR(f"Ambiguous slug {slug_q!r}: {len(matches)} matches"))
                for f in matches[:10]:
                    self.stdout.write(f"  id={f.id} name={f.name!r} slug={f.slug}")
                return None
            return matches[0]

        self.stderr.write("Provide --franchise-id, --franchise-name, or --franchise-slug")
        return None
