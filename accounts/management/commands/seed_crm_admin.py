"""
Create CRM super-admin logins (national access — all zones, all leads).

  python manage.py seed_crm_admin
  python manage.py seed_crm_admin --force-password
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import UserRole

User = get_user_model()

# National CRM admins — empty crm_zone / crm_region = Super Admin (all India).
CRM_SUPER_ADMINS = (
    {
        "email": "admin@timekids.com",
        "name": "CRM Super Admin",
        "password": "Admin@123",
    },
    {
        "email": "jayesh@time4education.com",
        "name": "Jayesh",
        "password": "Jayesh@Crm47",
    },
    {
        "email": "bethleena@timekidspreschools.com",
        "name": "Bethleena",
        "password": "Bethleena@Crm62",
    },
)


class Command(BaseCommand):
    help = "Seed CRM super-admin logins (national / all-India access)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force-password",
            action="store_true",
            help="Reset passwords for all super-admin accounts that already exist",
        )

    def handle(self, *args, **options):
        force_password = bool(options.get("force_password"))

        for entry in CRM_SUPER_ADMINS:
            email = (entry["email"] or "").strip().lower()
            password = entry["password"] or ""
            name = (entry.get("name") or "").strip() or "CRM Super Admin"

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
                        f"CRM super admin ready: {email} (password updated={force_password})"
                    )
                )
                continue

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
            self.stdout.write(self.style.SUCCESS(f"Created CRM super admin: {email} / {password}"))

        self.stdout.write(self.style.NOTICE("Super admins: national access (all zones, all lead types)."))
