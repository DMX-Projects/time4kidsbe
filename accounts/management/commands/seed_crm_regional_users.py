"""
Seed CRM regional logins — 2 regions per zone (NORTH/SOUTH/EAST/WEST).

  python manage.py seed_crm_regional_users
  python manage.py seed_crm_regional_users --force-password
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.crm_zones import REGION_LABELS, REGION_PARENT_ZONE, REGION_STATE_CODES, scope_display_state_names
from accounts.models import UserRole

User = get_user_model()

REGIONAL_USERS = (
    {
        "email": "north.r1.crm@timekids.com",
        "name": "CRM North Region 1",
        "region": "NORTH_R1",
        "password": "NorthR1@Crm1",
    },
    {
        "email": "north.r2.crm@timekids.com",
        "name": "CRM North Region 2",
        "region": "NORTH_R2",
        "password": "NorthR2@Crm1",
    },
    {
        "email": "south.r1.crm@timekids.com",
        "name": "CRM South Region 1",
        "region": "SOUTH_R1",
        "password": "SouthR1@Crm1",
    },
    {
        "email": "south.r2.crm@timekids.com",
        "name": "CRM South Region 2",
        "region": "SOUTH_R2",
        "password": "SouthR2@Crm1",
    },
    {
        "email": "east.r1.crm@timekids.com",
        "name": "CRM East Region 1",
        "region": "EAST_R1",
        "password": "EastR1@Crm1",
    },
    {
        "email": "east.r2.crm@timekids.com",
        "name": "CRM East Region 2",
        "region": "EAST_R2",
        "password": "EastR2@Crm1",
    },
    {
        "email": "west.r1.crm@timekids.com",
        "name": "CRM West Region 1",
        "region": "WEST_R1",
        "password": "WestR1@Crm1",
    },
    {
        "email": "west.r2.crm@timekids.com",
        "name": "CRM West Region 2",
        "region": "WEST_R2",
        "password": "WestR2@Crm1",
    },
)


class Command(BaseCommand):
    help = "Seed CRM regional users (2 regions per zone) with state-level scope."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force-password",
            action="store_true",
            help="Reset password if the user already exists",
        )

    def handle(self, *args, **options):
        force_password = bool(options.get("force_password"))

        for item in REGIONAL_USERS:
            email = item["email"]
            password = item["password"]
            region = item["region"]
            zone = REGION_PARENT_ZONE[region]
            user = User.objects.filter(email__iexact=email).first()
            if user:
                user.role = UserRole.CRM
                user.crm_zone = zone
                user.crm_region = region
                user.full_name = item["name"]
                user.is_active = True
                if force_password:
                    user.set_password(password)
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Updated: {email} / {password} region={region} "
                        f"(password updated={force_password})"
                    )
                )
            else:
                User.objects.create_user(
                    email=email,
                    username=email,
                    password=password,
                    role=UserRole.CRM,
                    full_name=item["name"],
                    crm_zone=zone,
                    crm_region=region,
                    is_active=True,
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Created: {email} / {password} region={region}")
                )

        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("Regional CRM logins (/crm-admin/login):"))
        for item in REGIONAL_USERS:
            region = item["region"]
            states = ", ".join(scope_display_state_names(list(REGION_STATE_CODES[region])))
            label = REGION_LABELS.get(region, region)
            self.stdout.write(
                f"  {label:<18} {item['email']:<32} / {item['password']:<14} -> {states}"
            )
