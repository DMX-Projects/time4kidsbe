"""
Create the default website content admin user.

  python manage.py seed_content_admin
  python manage.py seed_content_admin --password "Admin@123"
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import UserRole

User = get_user_model()

DEFAULT_EMAIL = "contentadmin@gmail.com"
DEFAULT_PASSWORD = "Admin@123"
DEFAULT_NAME = "Website Content Admin"


class Command(BaseCommand):
    help = "Seed website content admin login (contentadmin@gmail.com)."

    def add_arguments(self, parser):
        parser.add_argument("--email", default=DEFAULT_EMAIL, help="Content admin email")
        parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Content admin password")
        parser.add_argument("--name", default=DEFAULT_NAME, help="Full name")
        parser.add_argument(
            "--force-password",
            action="store_true",
            help="Reset password if the content admin already exists",
        )

    def handle(self, *args, **options):
        email = (options["email"] or DEFAULT_EMAIL).strip().lower()
        password = options["password"] or DEFAULT_PASSWORD
        name = (options.get("name") or DEFAULT_NAME).strip()
        force_password = bool(options.get("force_password"))

        user = User.objects.filter(email__iexact=email).first()
        if user:
            user.role = UserRole.ADMIN
            user.is_active = True
            user.is_staff = True
            user.is_superuser = False
            user.full_name = name or user.full_name
            if force_password:
                user.set_password(password)
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Content admin ready: {email} (password updated={force_password})"
                )
            )
            return

        User.objects.create_user(
            email=email,
            username=email,
            password=password,
            role=UserRole.ADMIN,
            full_name=name,
            is_active=True,
            is_staff=True,
            is_superuser=False,
        )
        self.stdout.write(self.style.SUCCESS(f"Created content admin: {email} / {password}"))
