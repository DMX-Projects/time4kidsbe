"""
Seed agency CRM viewers (view-only, no mobile/email, Dashboard only).

  Bcwebwise Agency — 6 states landing + Facebook/Meta Instant Forms
  Ants Agency — West Bengal city landing pages only

  python manage.py seed_crm_agency_viewers
  python manage.py seed_crm_agency_viewers --force-password
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import UserRole
from enquiries.crm_api import AGENCY_VIEWER_LABELS, AGENCY_VIEWER_STATES

User = get_user_model()

AGENCY_ACCOUNTS = (
    {
        "email": "bcwebwise.agency@gmail.com",
        "password": "TkBcww#View629",
    },
    {
        "email": "ants.agency@gmail.com",
        "password": "TkAnts#View384",
    },
)


class Command(BaseCommand):
    help = "Seed Bcwebwise + Ants agency CRM viewer logins."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force-password",
            action="store_true",
            help="Reset password if the account already exists",
        )

    def handle(self, *args, **options):
        force_password = bool(options.get("force_password"))

        for item in AGENCY_ACCOUNTS:
            email = item["email"].strip().lower()
            password = item["password"]
            name = AGENCY_VIEWER_LABELS.get(email) or "Agency Viewer"
            states = AGENCY_VIEWER_STATES.get(email) or ()
            crm_states = ",".join(states)

            user = User.objects.filter(email__iexact=email).first()
            if user:
                user.role = UserRole.CRM
                user.is_active = True
                user.full_name = name
                user.crm_zone = ""
                user.crm_region = ""
                user.crm_states = crm_states
                user.crm_cities = ""
                if force_password:
                    user.set_password(password)
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Agency ready: {email} ({name}) states={crm_states} "
                        f"password_updated={force_password}"
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
                    crm_states=crm_states,
                    crm_cities="",
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created agency: {email} / {password} ({name}) states={crm_states}"
                    )
                )

        self.stdout.write(
            self.style.NOTICE(
                "Access: Bcwebwise = landing + Facebook/Meta (6 states); "
                "Ants = West Bengal landing only · no mobile/email · view-only · "
                "login /crm-admin/login"
            )
        )
