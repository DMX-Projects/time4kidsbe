"""
Seed third-party Paid Campaign viewer (no mobile/email, view-only).

  python manage.py seed_crm_campaign_viewer
  python manage.py seed_crm_campaign_viewer --force-password
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import UserRole

User = get_user_model()

VIEWER = {
    "email": "campaign.viewer@gmail.com",
    "name": "Campaign External Viewer",
    "password": "TkView#Camp847",
}

# Old placeholder — deactivate if present so only the official login is used.
LEGACY_VIEWER_EMAILS = (
    "campaign.viewer@timekidspreschools.com",
)


class Command(BaseCommand):
    help = "Seed CRM Paid Campaign external viewer login."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force-password",
            action="store_true",
            help="Reset password if the account already exists",
        )

    def handle(self, *args, **options):
        force_password = bool(options.get("force_password"))
        email = VIEWER["email"].strip().lower()
        password = VIEWER["password"]
        name = VIEWER["name"]

        user = User.objects.filter(email__iexact=email).first()
        if user:
            user.role = UserRole.CRM
            user.is_active = True
            user.full_name = name
            user.crm_zone = ""
            user.crm_region = ""
            user.crm_states = ""
            if force_password:
                user.set_password(password)
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Campaign viewer ready: {email} (password updated={force_password})"
                )
            )
        else:
            User.objects.create_user(
                email=email,
                username=email,
                password=password,
                role=UserRole.CRM,
                full_name=name,
                is_active=True,
                crm_zone="",
                crm_region="",
                crm_states="",
            )
            self.stdout.write(
                self.style.SUCCESS(f"Created campaign viewer: {email} / {password}")
            )

        for legacy in LEGACY_VIEWER_EMAILS:
            legacy_user = User.objects.filter(email__iexact=legacy).first()
            if legacy_user and legacy_user.is_active:
                legacy_user.is_active = False
                legacy_user.save(update_fields=["is_active"])
                self.stdout.write(self.style.WARNING(f"Deactivated legacy viewer: {legacy}"))

        self.stdout.write(
            self.style.NOTICE(
                "Access: Paid Campaign + Reports only · no mobile/email · view-only · login /crm-admin/login"
            )
        )
