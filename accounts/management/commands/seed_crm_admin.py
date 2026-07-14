"""
Create the default CRM admin user (same as timekids_crm_clone seed).

  python manage.py seed_crm_admin
  python manage.py seed_crm_admin --password "Admin@123"
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import UserRole

User = get_user_model()

DEFAULT_EMAIL = "admin@timekids.com"
DEFAULT_PASSWORD = "Admin@123"
DEFAULT_NAME = "CRM Super Admin"


class Command(BaseCommand):
    help = "Seed default CRM admin login (admin@timekids.com) like timekids_crm_clone."

    def add_arguments(self, parser):
        parser.add_argument("--email", default=DEFAULT_EMAIL, help="CRM admin email")
        parser.add_argument("--password", default=DEFAULT_PASSWORD, help="CRM admin password")
        parser.add_argument("--name", default=DEFAULT_NAME, help="Full name")
        parser.add_argument(
            "--force-password",
            action="store_true",
            help="Reset password if the CRM admin already exists",
        )

    def handle(self, *args, **options):
        email = (options["email"] or DEFAULT_EMAIL).strip().lower()
        password = options["password"] or DEFAULT_PASSWORD
        name = (options.get("name") or DEFAULT_NAME).strip()
        force_password = bool(options.get("force_password"))

        user = User.objects.filter(email__iexact=email).first()
        if user:
            user.role = UserRole.CRM
            user.is_active = True
            user.full_name = name or user.full_name
            user.crm_zone = ""
            user.crm_region = ""
            if force_password:
                user.set_password(password)
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"CRM admin ready: {email} (password updated={force_password})"
                )
            )
            return

        User.objects.create_user(
            email=email,
            username=email,
            password=password,
            role=UserRole.CRM,
            full_name=name,
            is_active=True,
            crm_zone="",
            crm_region="",
        )
        self.stdout.write(self.style.SUCCESS(f"Created CRM admin: {email} / {password}"))
