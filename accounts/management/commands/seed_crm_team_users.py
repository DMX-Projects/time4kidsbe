"""
Seed real CRM team users from franchise/admission mapping sheets.

  python manage.py seed_crm_team_users
  python manage.py seed_crm_team_users --force-password

New-lead emails:
  - Franchise → pink Franchise sheet heads (crm_notify_franchise)
  - Admission → pink Admission sheet heads (crm_notify_admission)
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import UserRole

User = get_user_model()

DEFAULT_PASSWORD = "TimeKids@Crm1"

KERALA_ALL = (
    "Kasaragod,Kannur,Malappuram,Kozhikode,Wayanad,Thrissur,Palakkad,"
    "Ernakulam,Kottayam,Alappuzha,Kollam,Trivandrum,Pathanamthitta,Idukki"
)
KERALA_NORTH = "Kasaragod,Kannur,Malappuram,Kozhikode,Wayanad,Thrissur,Palakkad"
KERALA_SOUTH = "Ernakulam,Kottayam,Alappuzha,Kollam,Trivandrum,Pathanamthitta,Idukki"

# One account per person (Option A) — union of franchise + admission sheets.
# Pink rows on both sheets: Tejbal, Sujee, Gaurav, Jyoti.
TEAM_USERS = (
    {
        "email": "tejbal@timekidspreschools.com",
        "name": "Tejbal Singh",
        "zone": "SOUTH",
        "states": "AP,TG",
        "cities": "",
        "notify_franchise": True,
        "notify_admission": True,
    },
    {
        "email": "saikishore@timekidspreschools.com",
        "name": "Sai Kishore",
        "zone": "SOUTH",
        "states": "AP,TG",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "harshit@timekidspreschools.com",
        "name": "Harshit Katare",
        "zone": "SOUTH",
        "states": "AP,TG",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "sujee@timekidspreschools.com",
        "name": "Sujee",
        "zone": "SOUTH",
        "states": "KA",
        "cities": "",
        "notify_franchise": True,
        "notify_admission": True,
    },
    {
        "email": "thimmesh.k@timekidspreschools.com",
        "name": "Thimmesh",
        "zone": "SOUTH",
        "states": "KA",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "gaurav@timekidspreschools.com",
        "name": "Gaurav Grover",
        "zone": "SOUTH",
        "states": "TN,KL,MH",
        "cities": "",
        "notify_franchise": True,
        "notify_admission": True,
    },
    {
        "email": "jayaraj@timekidspreschools.com",
        "name": "M. Jayaraj",
        "zone": "SOUTH",
        "states": "TN",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "sivaraman@timekidspreschools.com",
        "name": "Sivaraman",
        "zone": "SOUTH",
        "states": "TN",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "joejoseph@timekidspreschools.com",
        "name": "Joe",
        "zone": "SOUTH",
        "states": "KL",
        "cities": KERALA_ALL,
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "satishmenon@timekidspreschools.com",
        "name": "Satish Menon",
        "zone": "SOUTH",
        "states": "KL",
        "cities": KERALA_SOUTH,
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "anoopkunjan@timekidspreschools.com",
        "name": "Anoop Kunjan",
        "zone": "SOUTH",
        "states": "KL",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "vivek@timekidspreschools.com",
        "name": "Vivek RT",
        "zone": "SOUTH",
        "states": "KL",
        "cities": KERALA_NORTH,
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "deepaknikam@timekidspreschools.com",
        "name": "Deepak Nikam",
        "zone": "WEST",
        "states": "MH",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "jyoti.mishra@timekidspreschools.com",
        "name": "Jyoti Mishra",
        "zone": "EAST",
        "states": "BR,CT,OR,JK",
        "cities": "",
        "notify_franchise": True,
        "notify_admission": True,
    },
)

PLACEHOLDER_EMAILS = (
    "north.crm@timekids.com",
    "south.crm@timekids.com",
    "east.crm@timekids.com",
    "west.crm@timekids.com",
    "north.r1.crm@timekids.com",
    "north.r2.crm@timekids.com",
    "south.r1.crm@timekids.com",
    "south.r2.crm@timekids.com",
    "east.r1.crm@timekids.com",
    "east.r2.crm@timekids.com",
    "west.r1.crm@timekids.com",
    "west.r2.crm@timekids.com",
)


class Command(BaseCommand):
    help = "Seed CRM team users from franchise/admission region mapping."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force-password",
            action="store_true",
            help="Reset password for existing users",
        )
        parser.add_argument(
            "--keep-placeholders",
            action="store_true",
            help="Do not deactivate old North/South zone placeholder accounts",
        )

    def handle(self, *args, **options):
        force_password = bool(options.get("force_password"))
        keep_placeholders = bool(options.get("keep_placeholders"))

        for item in TEAM_USERS:
            email = item["email"].strip().lower()
            user = User.objects.filter(email__iexact=email).first()
            notify_f = bool(item.get("notify_franchise"))
            notify_a = bool(item.get("notify_admission"))
            fields = {
                "role": UserRole.CRM,
                "full_name": item["name"],
                "crm_zone": item["zone"],
                "crm_region": "",
                "crm_states": item["states"],
                "crm_cities": item["cities"],
                "crm_notify_franchise": notify_f,
                "crm_notify_admission": notify_a,
                # Keep legacy flag in sync for any old code paths
                "crm_notify_leads": notify_f or notify_a,
                "is_active": True,
            }
            if user:
                for key, value in fields.items():
                    setattr(user, key, value)
                if force_password:
                    user.set_password(DEFAULT_PASSWORD)
                user.save()
                action = "Updated"
            else:
                User.objects.create_user(
                    email=email,
                    username=email,
                    password=DEFAULT_PASSWORD,
                    **fields,
                )
                action = "Created"
            flags = []
            if notify_f:
                flags.append("franchise")
            if notify_a:
                flags.append("admission")
            flag_txt = "+".join(flags) if flags else "none"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{action}: {item['name']} <{email}> states={item['states']} "
                    f"(notify={flag_txt})"
                )
            )

        if not keep_placeholders:
            deactivated = (
                User.objects.filter(role__iexact=UserRole.CRM.value, email__in=PLACEHOLDER_EMAILS)
                .exclude(email__iexact="admin@timekids.com")
                .update(is_active=False)
            )
            self.stdout.write(self.style.WARNING(f"Deactivated placeholder CRM users: {deactivated}"))

        self.stdout.write("")
        self.stdout.write(self.style.NOTICE(f"Default password: {DEFAULT_PASSWORD}"))
        self.stdout.write(self.style.NOTICE("Super Admin unchanged: admin@timekids.com"))
        self.stdout.write(
            self.style.NOTICE(
                "Emails: Franchise + Admission pink heads "
                "(Tejbal, Sujee, Gaurav, Jyoti)."
            )
        )
