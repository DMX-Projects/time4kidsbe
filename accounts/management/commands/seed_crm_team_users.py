"""
Seed real CRM team users from franchise/admission mapping sheets.

Sheet-shaped columns on ``users``:
  email, full_name, crm_designation, crm_mapping_region, crm_phone,
  crm_states (full names), crm_cities, password (hashed — never store plain text).

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

KERALA_NORTH = "Kasaragod,Kannur,Malappuram,Kozhikode,Wayanad,Thrissur,Palakkad"
KERALA_SOUTH = "Ernakulam,Kottayam,Alappuzha,Kollam,Trivandrum,Pathanamthitta,Idukki"

# One account per person — union of franchise + admission sheets.
# ``mapping_region`` = Region column on the sheet.
# ``phone`` = leave blank until ops provides numbers.
# ``password`` is set via set_password (hashed in DB).
TEAM_USERS = (
    {
        "email": "tejbal@timekidspreschools.com",
        "name": "Tejbal Singh",
        "password": "Tejbal@Crm74",
        "designation": "Zonal Manager",
        "mapping_region": "AP/TS/KA",
        "phone": "7989281696",
        "zone": "SOUTH",
        "states": "Andhra Pradesh, Telangana, Karnataka",
        "cities": "",
        "notify_franchise": True,
        "notify_admission": True,
    },
    {
        "email": "saikishore@timekidspreschools.com",
        "name": "Sai Kishore",
        "password": "SaiKish@Crm19",
        "designation": "Dy Manager",
        "mapping_region": "AP/TS",
        "phone": "8639142466",
        "zone": "SOUTH",
        "states": "Andhra Pradesh, Telangana",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "harshit@timekidspreschools.com",
        "name": "Harshit Katare",
        "password": "Harshit@Crm58",
        "designation": "Assistant Manager",
        "mapping_region": "AP/TS",
        "phone": "9966499776",
        "zone": "SOUTH",
        "states": "Andhra Pradesh, Telangana",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "sujee@timekidspreschools.com",
        "name": "Sujee",
        "password": "Sujee@Crm83",
        "designation": "Regional Manager",
        "mapping_region": "KA",
        "phone": "8888807788",
        "zone": "SOUTH",
        "states": "Karnataka",
        "cities": "",
        "notify_franchise": True,
        "notify_admission": True,
    },
    {
        "email": "thimmesh.k@timekidspreschools.com",
        "name": "Thimmesh",
        "password": "Thimmesh@Crm27",
        "designation": "Manager",
        "mapping_region": "KA",
        "phone": "",
        "zone": "SOUTH",
        "states": "Karnataka",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "gaurav@timekidspreschools.com",
        "name": "Gaurav Grover",
        "password": "Gaurav@Crm91",
        "designation": "Zonal Manager",
        "mapping_region": "TN/KL/MH",
        "phone": "9884035596",
        "zone": "SOUTH",
        "states": "Tamil Nadu, Kerala, Maharashtra",
        "cities": "",
        "notify_franchise": True,
        "notify_admission": True,
    },
    {
        "email": "jayaraj@timekidspreschools.com",
        "name": "M. Jayaraj",
        "password": "Jayaraj@Crm46",
        "designation": "Manager",
        "mapping_region": "Tamil Nadu",
        "phone": "8012133111",
        "zone": "SOUTH",
        "states": "Tamil Nadu",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "sivaraman@timekidspreschools.com",
        "name": "Sivaraman",
        "password": "Sivaraman@Crm12",
        "designation": "Assistant Manager",
        "mapping_region": "Tamil Nadu",
        "phone": "",
        "zone": "SOUTH",
        "states": "Tamil Nadu",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "joejoseph@timekidspreschools.com",
        "name": "Joe",
        "password": "JoeJoseph@Crm65",
        "designation": "Regional Manager",
        "mapping_region": "Kerala",
        "phone": "9074586895",
        "zone": "SOUTH",
        "states": "Kerala",
        # Regional Manager covers all Kerala and can assign to Satish/Vivek by territory.
        "cities": "",
        "notify_franchise": True,
        "notify_admission": True,
    },
    {
        "email": "satishmenon@timekidspreschools.com",
        "name": "Satish Menon",
        "password": "Satish@Crm88",
        "designation": "Manager",
        "mapping_region": "Kerala",
        "phone": "8089001116",
        "zone": "SOUTH",
        "states": "Kerala",
        "cities": KERALA_SOUTH,
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "anoopkunjan@timekidspreschools.com",
        "name": "Anoop Kunjan",
        "password": "Anoop@Crm34",
        "designation": "Assistant Manager",
        "mapping_region": "Kerala",
        "phone": "",
        "zone": "SOUTH",
        "states": "Kerala",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "vivek@timekidspreschools.com",
        "name": "Vivek RT",
        "password": "Vivek@Crm57",
        "designation": "Manager",
        "mapping_region": "Kerala",
        "phone": "7907467952",
        "zone": "SOUTH",
        "states": "Kerala",
        "cities": KERALA_NORTH,
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "deepaknikam@timekidspreschools.com",
        "name": "Deepak Nikam",
        "password": "Deepak@Crm22",
        "designation": "Assistant Manager",
        "mapping_region": "Maharashtra",
        "phone": "",
        "zone": "WEST",
        "states": "Maharashtra",
        "cities": "",
        "notify_franchise": False,
        "notify_admission": False,
    },
    {
        "email": "jyoti.mishra@timekidspreschools.com",
        "name": "Jyoti Mishra",
        "password": "Jyoti@Crm79",
        "designation": "Zonal Manager",
        "mapping_region": "East",
        "phone": "8335807272",
        "zone": "EAST",
        "states": "Bihar, Chhattisgarh, Odisha, West Bengal",
        "cities": (
            "Patna,Bhadrak,Bhubaneswar,Cuttack,Khurda,"
            "Asansol,Barasat,Durgapur,Hooghly,Howrah,Kolkata,Siliguri"
        ),
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
                "crm_designation": (item.get("designation") or "").strip(),
                "crm_mapping_region": (item.get("mapping_region") or "").strip(),
                "crm_phone": (item.get("phone") or "").strip(),
                "crm_zone": item["zone"],
                "crm_region": "",
                "crm_states": item["states"],
                "crm_cities": item["cities"],
                "crm_notify_franchise": notify_f,
                "crm_notify_admission": notify_a,
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
                    f"{action}: {item['name']} <{email}> "
                    f"region={item.get('mapping_region')} "
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
        self.stdout.write(self.style.NOTICE("Unique passwords per user (hashed in DB; Super Admin unchanged):"))
        self.stdout.write(self.style.NOTICE("  admin@timekids.com / Admin@123"))
        for item in TEAM_USERS:
            self.stdout.write(f"  {item['email']:<40} / {item['password']}")
        self.stdout.write(
            self.style.NOTICE(
                "Emails: Franchise + Admission pink heads "
                "(Tejbal, Sujee, Gaurav, Jyoti)."
            )
        )
        self.stdout.write(
            self.style.NOTICE(
                "Phone: crm_phone filled from sheet where provided "
                "(empty for Deepak / Thimmesh / Sivaraman / Anoop until shared)."
            )
        )
