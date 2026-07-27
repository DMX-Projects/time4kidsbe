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

KERALA_ALL = (
    "Kasaragod,Kannur,Malappuram,Kozhikode,Wayanad,Thrissur,Palakkad,"
    "Ernakulam,Kottayam,Alappuzha,Kollam,Trivandrum,Pathanamthitta,Idukki"
)
KERALA_NORTH = "Kasaragod,Kannur,Malappuram,Kozhikode,Wayanad,Thrissur,Palakkad"
KERALA_SOUTH = "Ernakulam,Kottayam,Alappuzha,Kollam,Trivandrum,Pathanamthitta,Idukki"

# One account per person (Option A) — union of franchise + admission sheets.
# Pink rows on both sheets: Tejbal, Sujee, Gaurav, Jyoti.
# Unique password per user; Super Admin (admin@timekids.com) is never touched here.
TEAM_USERS = (
    {
        "email": "tejbal@timekidspreschools.com",
        "name": "Tejbal Singh",
        "password": "Tejbal@Crm74",
        "zone": "SOUTH",
        "states": "AP,TG",
        "cities": "",
        "notify_franchise": True,
        "notify_admission": True,
    },
    {
        "email": "saikishore@timekidspreschools.com",
        "name": "Sai Kishore",
        "password": "SaiKish@Crm19",
        "zone": "SOUTH",
        "states": "AP,TG",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "harshit@timekidspreschools.com",
        "name": "Harshit Katare",
        "password": "Harshit@Crm58",
        "zone": "SOUTH",
        "states": "AP,TG",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "sujee@timekidspreschools.com",
        "name": "Sujee",
        "password": "Sujee@Crm83",
        "zone": "SOUTH",
        "states": "KA",
        "cities": "",
        "notify_franchise": True,
        "notify_admission": True,
    },
    {
        "email": "thimmesh.k@timekidspreschools.com",
        "name": "Thimmesh",
        "password": "Thimmesh@Crm27",
        "zone": "SOUTH",
        "states": "KA",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "gaurav@timekidspreschools.com",
        "name": "Gaurav Grover",
        "password": "Gaurav@Crm91",
        "zone": "SOUTH",
        "states": "TN,KL,MH",
        "cities": "",
        "notify_franchise": True,
        "notify_admission": True,
    },
    {
        "email": "jayaraj@timekidspreschools.com",
        "name": "M. Jayaraj",
        "password": "Jayaraj@Crm46",
        "zone": "SOUTH",
        "states": "TN",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "sivaraman@timekidspreschools.com",
        "name": "Sivaraman",
        "password": "Sivaraman@Crm12",
        "zone": "SOUTH",
        "states": "TN",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "joejoseph@timekidspreschools.com",
        "name": "Joe",
        "password": "JoeJoseph@Crm65",
        "zone": "SOUTH",
        "states": "KL",
        "cities": KERALA_ALL,
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "satishmenon@timekidspreschools.com",
        "name": "Satish Menon",
        "password": "Satish@Crm88",
        "zone": "SOUTH",
        "states": "KL",
        "cities": KERALA_SOUTH,
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "anoopkunjan@timekidspreschools.com",
        "name": "Anoop Kunjan",
        "password": "Anoop@Crm34",
        "zone": "SOUTH",
        "states": "KL",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "vivek@timekidspreschools.com",
        "name": "Vivek RT",
        "password": "Vivek@Crm57",
        "zone": "SOUTH",
        "states": "KL",
        "cities": KERALA_NORTH,
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "deepaknikam@timekidspreschools.com",
        "name": "Deepak Nikam",
        "password": "Deepak@Crm22",
        "zone": "WEST",
        "states": "MH",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "jyoti.mishra@timekidspreschools.com",
        "name": "Jyoti Mishra",
        "password": "Jyoti@Crm79",
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
            password = item["password"]
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
                    user.set_password(password)
                user.save()
                action = "Updated"
            else:
                User.objects.create_user(
                    email=email,
                    username=email,
                    password=password,
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
                    f"{action}: {item['name']} <{email}> / {password} "
                    f"states={item['states']} (notify={flag_txt})"
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
        self.stdout.write(self.style.NOTICE("Unique passwords per user (Super Admin unchanged):"))
        self.stdout.write(self.style.NOTICE("  admin@timekids.com / Admin@123"))
        for item in TEAM_USERS:
            self.stdout.write(f"  {item['email']:<40} / {item['password']}")
        self.stdout.write(
            self.style.NOTICE(
                "Emails: Franchise + Admission pink heads "
                "(Tejbal, Sujee, Gaurav, Jyoti)."
            )
        )
