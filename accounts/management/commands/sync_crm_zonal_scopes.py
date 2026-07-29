"""
Write ZONAL_MANAGER_SCOPE_CODES (+ seed team territories) onto User.crm_states / crm_zone.

Run on production after deploy so Jyoti etc. never get the national state list
(including Jammu and Kashmir):

  python manage.py sync_crm_zonal_scopes
"""

from django.core.management.base import BaseCommand

from accounts.crm_zones import ZONAL_MANAGER_SCOPE_CODES, CrmZone
from accounts.models import User, UserRole


# Email → (zone, comma state codes) — must match seed_crm_team_users / product map.
TEAM_SCOPES: dict[str, tuple[str, str]] = {
    "jyoti.mishra@timekidspreschools.com": (CrmZone.EAST, "BR,CT,OR,WB"),
    "tejbal@timekidspreschools.com": (CrmZone.SOUTH, "AP,TG,KA"),
    "gaurav@timekidspreschools.com": (CrmZone.SOUTH, "TN,KL,MH"),
}


class Command(BaseCommand):
    help = "Sync CRM zonal manager territory (crm_zone / crm_states) from the code map."

    def handle(self, *args, **options):
        emails = set(ZONAL_MANAGER_SCOPE_CODES) | set(TEAM_SCOPES)
        fixed = 0
        missing = 0
        for email in sorted(emails):
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                self.stdout.write(self.style.WARNING(f"missing user: {email}"))
                missing += 1
                continue

            zone, states = TEAM_SCOPES.get(email.lower(), (None, None))
            if not states:
                codes = ZONAL_MANAGER_SCOPE_CODES.get(email.lower()) or ()
                states = ",".join(codes)
            if not zone:
                # Infer zone from first code when only map codes exist
                from accounts.crm_zones import ZONE_STATE_CODES

                code_set = set((states or "").split(","))
                zone = ""
                for z, zcodes in ZONE_STATE_CODES.items():
                    if code_set & set(zcodes):
                        zone = z
                        break

            user.role = UserRole.CRM
            user.crm_zone = zone or user.crm_zone or ""
            user.crm_states = states
            user.is_active = True
            user.save(update_fields=["role", "crm_zone", "crm_states", "is_active"])
            fixed += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"updated {email}: zone={user.crm_zone} states={user.crm_states}"
                )
            )

        self.stdout.write(self.style.NOTICE(f"done: updated={fixed} missing={missing}"))
