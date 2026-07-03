from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from accounts.models import UserRole

User = get_user_model()


class Command(BaseCommand):
    help = "Create or update a CRM-only login for /crm-admin."

    def add_arguments(self, parser):
        parser.add_argument("email", help="CRM user email address")
        parser.add_argument("--password", required=True, help="Password for the CRM user")
        parser.add_argument("--name", default="", help="Full name")
        parser.add_argument(
            "--update-password",
            action="store_true",
            help="Update the password if this CRM user already exists",
        )

    def handle(self, *args, **options):
        email = (options["email"] or "").strip().lower()
        password = options["password"] or ""
        name = (options.get("name") or "").strip()

        if not email:
            raise CommandError("Email is required.")
        if len(password) < 8:
            raise CommandError("Password must be at least 8 characters.")

        user = User.objects.filter(email__iexact=email).first()
        if user:
            user.role = UserRole.CRM
            user.is_active = True
            if name:
                user.full_name = name
            if options["update_password"]:
                user.set_password(password)
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated CRM user {email}. "
                    f"Password changed={bool(options['update_password'])}"
                )
            )
            return

        User.objects.create_user(
            email=email,
            username=email,
            password=password,
            role=UserRole.CRM,
            full_name=name or "CRM User",
            is_active=True,
        )
        self.stdout.write(self.style.SUCCESS(f"Created CRM user {email}"))
