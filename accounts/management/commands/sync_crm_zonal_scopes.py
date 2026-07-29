"""
Write ZONAL_MANAGER_SCOPE_CODES (+ seed team territories) onto User.crm_states / crm_zone.

Stores full state names (CRM display names), not TN/KL codes.

  python manage.py sync_crm_zonal_scopes
"""

from django.core.management.base import BaseCommand

from accounts.crm_zones import STATE_CODE_TO_NAME, ZONAL_MANAGER_SCOPE_CODES, CrmZone
from accounts.models import User, UserRole


def _codes_to_display(codes: str | tuple[str, ...] | list[str]) -> str:
    if isinstance(codes, str):
        parts = [p.strip() for p in codes.split(",") if p.strip()]
    else:
        parts = [str(p).strip() for p in codes if str(p).strip()]
    names: list[str] = []
    seen: set[str] = set()
    for part in parts:
        upper = part.upper()
        if upper in STATE_CODE_TO_NAME:
            name = STATE_CODE_TO_NAME[upper]
        else:
            # Already a display name / alias — keep as-is if known, else title-case
            name = STATE_CODE_TO_NAME.get(upper) or part
            from franchises.franchise_geo import state_to_code, state_to_display

            code = state_to_code(part)
            name = state_to_display(part) if code else part
        key = name.casefold()
        if key not in seen:
            seen.add(key)
            names.append(name)
    return ", ".join(names)


# Email → (zone, full state names, designation)
TEAM_SCOPES: dict[str, tuple[str, str, str]] = {
    "jyoti.mishra@timekidspreschools.com": (
        CrmZone.EAST,
        "Bihar, Chhattisgarh, Odisha, West Bengal",
        "Zonal Manager",
    ),
    "tejbal@timekidspreschools.com": (
        CrmZone.SOUTH,
        "Andhra Pradesh, Telangana, Karnataka",
        "Zonal Manager",
    ),
    "gaurav@timekidspreschools.com": (
        CrmZone.SOUTH,
        "Tamil Nadu, Kerala, Maharashtra",
        "Zonal Manager",
    ),
}


class Command(BaseCommand):
    help = "Sync CRM zonal manager territory (full state names + designation)."

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

            if email.lower() in TEAM_SCOPES:
                zone, states, designation = TEAM_SCOPES[email.lower()]
            else:
                codes = ZONAL_MANAGER_SCOPE_CODES.get(email.lower()) or ()
                states = _codes_to_display(codes)
                zone = ""
                designation = getattr(user, "crm_designation", "") or "Zonal Manager"
                from accounts.crm_zones import ZONE_STATE_CODES

                code_set = set(codes)
                for z, zcodes in ZONE_STATE_CODES.items():
                    if code_set & set(zcodes):
                        zone = z
                        break

            user.role = UserRole.CRM
            user.crm_zone = zone or user.crm_zone or ""
            user.crm_states = states
            if designation:
                user.crm_designation = designation
            user.is_active = True
            user.save(
                update_fields=[
                    "role",
                    "crm_zone",
                    "crm_states",
                    "crm_designation",
                    "is_active",
                ]
            )
            fixed += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"updated {email}: zone={user.crm_zone} "
                    f"designation={user.crm_designation} states={user.crm_states}"
                )
            )

        self.stdout.write(self.style.NOTICE(f"done: updated={fixed} missing={missing}"))
