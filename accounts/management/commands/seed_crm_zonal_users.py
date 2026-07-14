"""
Seed CRM zonal logins (EAST / WEST / NORTH / SOUTH).

  python manage.py seed_crm_zonal_users
  python manage.py seed_crm_zonal_users --force-password
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import CrmZone, UserRole

User = get_user_model()

ZONAL_USERS = (
    {
        "email": "north.crm@timekids.com",
        "name": "CRM North Zone",
        "zone": CrmZone.NORTH,
        "password": "North@Crm1",
    },
    {
        "email": "south.crm@timekids.com",
        "name": "CRM South Zone",
        "zone": CrmZone.SOUTH,
        "password": "South@Crm1",
    },
    {
        "email": "east.crm@timekids.com",
        "name": "CRM East Zone",
        "zone": CrmZone.EAST,
        "password": "East@Crm1",
    },
    {
        "email": "west.crm@timekids.com",
        "name": "CRM West Zone",
        "zone": CrmZone.WEST,
        "password": "West@Crm1",
    },
)


class Command(BaseCommand):
    help = "Seed CRM zonal users (NORTH/SOUTH/EAST/WEST) restricted to their states."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force-password",
            action="store_true",
            help="Reset password if the user already exists",
        )

    def handle(self, *args, **options):
        force_password = bool(options.get("force_password"))

        for item in ZONAL_USERS:
            email = item["email"]
            password = item["password"]
            user = User.objects.filter(email__iexact=email).first()
            if user:
                user.role = UserRole.CRM
                user.crm_zone = item["zone"]
                user.crm_region = ""
                user.full_name = item["name"]
                user.is_active = True
                if force_password:
                    user.set_password(password)
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Updated: {email} / {password} zone={item['zone']} "
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
                    crm_zone=item["zone"],
                    crm_region="",
                    is_active=True,
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Created: {email} / {password} zone={item['zone']}")
                )

        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("Zonal CRM logins (/crm-admin/login):"))
        for item in ZONAL_USERS:
            self.stdout.write(f"  {item['zone']:<6} {item['email']}  /  {item['password']}")
        self.stdout.write(
            self.style.NOTICE(
                "National CRM (all zones): admin@timekids.com / Admin@123"
            )
        )
