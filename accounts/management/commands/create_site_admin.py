"""
Create exactly one head-office admin (superuser, ADMIN role) if that email does not exist.

Safe for production: does not create, delete, or update franchise (centre) or parent users.
Use this when deploying to live where centres already have their own logins.

Examples:
  set DJANGO_CREATE_ADMIN_PASSWORD=your-secure-secret  python manage.py create_site_admin --email admin@yourdomain.com

  python manage.py create_site_admin --email admin@yourdomain.com --password 'use-strong-secret'
"""

from __future__ import annotations

import getpass
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Create a site admin (superuser) if the email is new. "
        "Never touches existing franchise or parent accounts."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            required=True,
            help="Login email for the admin (must not already exist).",
        )
        parser.add_argument(
            "--password",
            type=str,
            default="",
            help="Optional; prefer env DJANGO_CREATE_ADMIN_PASSWORD to avoid shell history.",
        )
        parser.add_argument(
            "--full-name",
            type=str,
            default="Site administrator",
            dest="full_name",
        )

    def handle(self, *args, **options):
        email = (options["email"] or "").strip().lower()
        if not email:
            raise CommandError("--email is required")

        if User.objects.filter(email__iexact=email).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"User already exists for {email} — skipping (no password change, no other users modified)."
                )
            )
            return

        password = (options["password"] or "").strip()
        if not password:
            password = (os.environ.get("DJANGO_CREATE_ADMIN_PASSWORD") or "").strip()
        if not password:
            password = getpass.getpass("Admin password (not echoed): ").strip()
        if len(password) < 8:
            raise CommandError("Password must be at least 8 characters.")

        User.objects.create_superuser(
            email=email,
            password=password,
            full_name=options["full_name"],
        )
        self.stdout.write(self.style.SUCCESS(f"Created site admin: {email} (role ADMIN). Franchise/parent users unchanged."))
