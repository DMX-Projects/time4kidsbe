"""CRM Users page (Super Admin): add / edit users, per-user leads, bulk transfer, activate / deactivate."""

from __future__ import annotations

import re
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from accounts.models import User, UserRole

from .crm_users import (
    CRM_ASSIGNABLE_DESIGNATIONS,
    CRM_ASSIGNABLE_HANDLER_EMAILS,
    CRM_SUPER_ADMIN_ASSIGN_EMAILS,
    CRM_SUPER_ADMIN_DESIGNATION,
    REGIONAL_MANAGER_ASSIGN_EMAILS,
    ZONAL_MANAGER_ASSIGN_EMAILS,
    crm_designation_for_user,
    display_name_for_user,
    is_national_crm_super_admin,
)
from .models import CrmLead, Enquiry, FranchiseEnquiry, KidsEnquiry, UnifiedLeadNote

# Finished pipelines — everything else counts as an open lead.
CLOSED_LEAD_STATUSES = frozenset(
    {
        "converted_admission",
        "converted_mou_signed",
        "converted_agreement_signed",
        "not_interested",
        "wrong_enquiry",
        "joined_competition",
    }
)

LEAD_KIND_LABELS = {
    "crm": "Franchise Campaign",
    "franchiseenquiry": "Franchise Enquiry",
    "enquiry": "Admission / Centre",
    "landing": "Admission Landing",
}

# Old shared zone / region logins replaced by the real team (kept disabled, hidden from the Users page).
CRM_PLACEHOLDER_EMAILS = (
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

LEAD_MODELS = {
    "crm": CrmLead,
    "enquiry": Enquiry,
    "franchiseenquiry": FranchiseEnquiry,
    "landing": KidsEnquiry,
}


def is_crm_super_admin(user) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return is_national_crm_super_admin(user)


def is_open_status(status: str | None) -> bool:
    return (status or "untouched").strip().lower() not in CLOSED_LEAD_STATUSES


def _landing_status(row: KidsEnquiry) -> str:
    payload = row.raw_payload if isinstance(row.raw_payload, dict) else {}
    return str(payload.get("crm_status") or "").strip() or "untouched"


def crm_team_users() -> list[User]:
    """Every CRM login that can hold leads (active and inactive), excluding viewer-only and placeholder accounts."""
    from .crm_api import is_restricted_crm_viewer

    users = (
        User.objects.filter(role__iexact=UserRole.CRM.value)
        .exclude(email__in=CRM_PLACEHOLDER_EMAILS)
        .select_related("crm_reports_to")
        .order_by("full_name", "email")
    )
    return [u for u in users if not is_restricted_crm_viewer(user=u)]


def lead_counts_by_user() -> dict[int, dict[str, int]]:
    counts: dict[int, dict[str, int]] = defaultdict(lambda: {"total": 0, "open": 0})

    for model in (CrmLead, Enquiry, FranchiseEnquiry):
        for user_id, lead_status in model.objects.filter(assigned_user__isnull=False).values_list(
            "assigned_user_id", "status"
        ):
            counts[user_id]["total"] += 1
            if is_open_status(lead_status):
                counts[user_id]["open"] += 1

    for row in KidsEnquiry.objects.filter(assigned_user__isnull=False).only("id", "assigned_user_id", "raw_payload"):
        counts[row.assigned_user_id]["total"] += 1
        if is_open_status(_landing_status(row)):
            counts[row.assigned_user_id]["open"] += 1

    return counts


def is_sheet_configured_user(user: User) -> bool:
    """Original team wired by email in crm_users — reporting line / pipelines are not editable here."""
    email = (user.email or "").strip().lower()
    return (
        email in CRM_ASSIGNABLE_HANDLER_EMAILS
        or email in ZONAL_MANAGER_ASSIGN_EMAILS
        or email in REGIONAL_MANAGER_ASSIGN_EMAILS
        or email in CRM_SUPER_ADMIN_ASSIGN_EMAILS
    )


def team_user_dict(user: User, counts: dict[int, dict[str, int]]) -> dict:
    c = counts.get(user.pk, {"total": 0, "open": 0})
    super_admin = is_crm_super_admin(user)
    reports_to = user.crm_reports_to if user.crm_reports_to_id else None
    return {
        "id": user.pk,
        "name": display_name_for_user(user),
        "fullName": (user.full_name or "").strip(),
        "email": user.email,
        "designation": crm_designation_for_user(user) or ("Super Admin" if super_admin else ""),
        "phone": (user.crm_phone or "").strip(),
        "states": (getattr(user, "crm_states", None) or "").strip(),
        "cities": (user.crm_cities or "").strip(),
        "reportsToId": user.crm_reports_to_id,
        "reportsToName": display_name_for_user(reports_to) if reports_to else "",
        "handlesFranchise": bool(user.crm_handles_franchise),
        "handlesAdmission": bool(user.crm_handles_admission),
        "sheetConfigured": is_sheet_configured_user(user),
        "canEdit": (user.email or "").strip().lower() not in CRM_SUPER_ADMIN_ASSIGN_EMAILS,
        "isActive": bool(user.is_active),
        "isSuperAdmin": super_admin,
        "totalLeads": c["total"],
        "openLeads": c["open"],
    }


def _manager_users() -> list[User]:
    emails = ZONAL_MANAGER_ASSIGN_EMAILS | REGIONAL_MANAGER_ASSIGN_EMAILS
    users = [
        u
        for u in User.objects.filter(role__iexact=UserRole.CRM.value, is_active=True)
        if (u.email or "").strip().lower() in emails
    ]
    return sorted(users, key=lambda u: (crm_designation_for_user(u) != "Zonal Manager", display_name_for_user(u)))


def _state_names() -> list[str]:
    from franchises.franchise_geo import STATE_CODE_TO_NAME

    return sorted(set(STATE_CODE_TO_NAME.values()), key=str.casefold)


def team_form_options() -> dict:
    return {
        "designations": [CRM_SUPER_ADMIN_DESIGNATION, *CRM_ASSIGNABLE_DESIGNATIONS],
        "managers": [
            {"id": u.pk, "name": display_name_for_user(u), "designation": crm_designation_for_user(u)}
            for u in _manager_users()
        ],
        "states": _state_names(),
    }


def _clean_list(raw) -> list[str]:
    items = raw if isinstance(raw, list) else str(raw or "").split(",")
    seen: dict[str, str] = {}
    for item in items:
        name = " ".join(str(item or "").split())
        if name:
            seen.setdefault(name.casefold(), name)
    return list(seen.values())


def _as_bool(raw) -> bool:
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def save_team_user(data: dict, user: User | None = None) -> tuple[User | None, dict[str, str]]:
    """
    Create (``user`` None) or update a CRM user from the Users page form.
    Returns ``(user, {})`` on success or ``(None, field_errors)``.
    """
    errors: dict[str, str] = {}
    creating = user is None
    team_editable = creating or not is_sheet_configured_user(user)
    designation = str(data.get("designation") or "").strip() if team_editable else None
    # Super Admins are national: no territory, manager or pipeline.
    super_admin = designation == CRM_SUPER_ADMIN_DESIGNATION

    full_name = " ".join(str(data.get("name") or "").split())
    if not full_name:
        errors["name"] = "Enter the name."

    email = str(data.get("email") or "").strip().lower()
    if creating:
        try:
            validate_email(email)
        except ValidationError:
            errors["email"] = "Enter a valid email address."
        else:
            if User.objects.filter(email__iexact=email).exists():
                errors["email"] = "A login with this email already exists."

    password = str(data.get("password") or "")
    if creating or password:
        if len(password) < 8:
            errors["password"] = "Password must be at least 8 characters."

    phone = re.sub(r"\D", "", str(data.get("phone") or ""))
    if len(phone) == 12 and phone.startswith("91"):
        phone = phone[2:]
    if phone and not re.fullmatch(r"[6-9]\d{9}", phone):
        errors["phone"] = "Enter a valid 10-digit mobile number."

    from franchises.franchise_geo import STATE_CODE_TO_NAME, state_to_code

    states: list[str] = []
    unknown: list[str] = []
    for raw_state in _clean_list(data.get("states")):
        name = STATE_CODE_TO_NAME.get(state_to_code(raw_state) or "")
        if not name:
            unknown.append(raw_state)
        elif name not in states:
            states.append(name)
    cities = _clean_list(data.get("cities"))
    if super_admin:
        states, cities = [], []
    elif unknown:
        errors["states"] = f"Unknown state: {', '.join(unknown)}."
    elif not states and team_editable:
        errors["states"] = "Select at least one state."

    reports_to = None
    handles_franchise = handles_admission = False
    if team_editable and not super_admin:
        if designation not in CRM_ASSIGNABLE_DESIGNATIONS:
            errors["designation"] = "Select a designation."
        managers = {u.pk: u for u in _manager_users()}
        try:
            reports_to = managers.get(int(data.get("reportsToId")))
        except (TypeError, ValueError):
            reports_to = None
        if reports_to is None:
            errors["reportsToId"] = "Select who this user reports to."
        handles_franchise = _as_bool(data.get("handlesFranchise"))
        handles_admission = _as_bool(data.get("handlesAdmission"))
        if not (handles_franchise or handles_admission):
            errors["pipelines"] = "Select Franchise, Admission or both."

    if errors:
        return None, errors

    with transaction.atomic():
        if creating:
            user = User(email=email, username=email, role=UserRole.CRM, is_active=True)
        user.full_name = full_name
        user.crm_phone = phone
        user.crm_states = ", ".join(states)
        user.crm_cities = ",".join(cities)
        if team_editable:
            user.crm_designation = designation
            user.crm_reports_to = reports_to
            user.crm_zone = reports_to.crm_zone or "" if reports_to else ""
            user.crm_region = ""
            user.crm_handles_franchise = handles_franchise
            user.crm_handles_admission = handles_admission
        if password:
            user.set_password(password)
        user.save()
    return user, {}


def _row(kind: str, pk: int, *, name, mobile, state, city, lead_status, created) -> dict:
    return {
        "id": f"{kind}-{pk}",
        "kind": kind,
        "kindLabel": LEAD_KIND_LABELS[kind],
        "name": name or "",
        "mobile": mobile or "",
        "state": state or "",
        "city": city or "",
        "status": lead_status or "untouched",
        "isOpen": is_open_status(lead_status),
        "createdAt": created.isoformat() if created else None,
    }


def leads_for_user(user_id: int) -> list[dict]:
    rows: list[dict] = []
    for lead in CrmLead.objects.filter(assigned_user_id=user_id):
        rows.append(
            _row("crm", lead.pk, name=lead.full_name, mobile=lead.mobile, state=lead.state,
                 city=lead.city, lead_status=lead.status, created=lead.created_at)
        )
    for enq in FranchiseEnquiry.objects.filter(assigned_user_id=user_id):
        rows.append(
            _row("franchiseenquiry", enq.pk, name=enq.name, mobile=enq.phone, state=enq.state,
                 city=enq.city, lead_status=enq.status, created=enq.created_at)
        )
    for enq in Enquiry.objects.filter(assigned_user_id=user_id).select_related("franchise"):
        franchise = enq.franchise if enq.franchise_id else None
        state = (getattr(franchise, "statename", None) or getattr(franchise, "state", None) or "") if franchise else ""
        rows.append(
            _row("enquiry", enq.pk, name=enq.name, mobile=enq.phone, state=state,
                 city=enq.city, lead_status=enq.status, created=enq.created_at)
        )
    for row in KidsEnquiry.objects.filter(assigned_user_id=user_id):
        rows.append(
            _row("landing", row.pk, name=row.name, mobile=row.mobileno or row.mobile, state=row.state,
                 city=row.city, lead_status=_landing_status(row), created=row.created_date)
        )
    rows.sort(key=lambda r: r["createdAt"] or "", reverse=True)
    return rows


def _parse_ids(lead_ids: list[str]) -> dict[str, set[int]]:
    from .crm_api import parse_lead_id

    wanted: dict[str, set[int]] = defaultdict(set)
    for raw in lead_ids:
        try:
            kind, pk = parse_lead_id(str(raw))
        except (TypeError, ValueError):
            continue
        if kind in LEAD_MODELS:
            wanted[kind].add(pk)
    return wanted


def transfer_leads(
    *,
    from_user: User,
    to_user: User,
    actor: User,
    lead_ids: list[str] | None = None,
    open_only: bool = True,
) -> int:
    """
    Move leads assigned to ``from_user`` onto ``to_user``.

    ``lead_ids`` limits the move to those leads (each must still belong to ``from_user``);
    otherwise every lead of ``from_user`` (open ones only when ``open_only``).
    Each moved lead gets its own History note; nothing outside the selected rows changes.
    """
    wanted = _parse_ids(lead_ids) if lead_ids else None
    stamp = timezone.localtime().strftime("%d %b %Y %H:%M")
    note_text = (
        f"Lead transferred from {display_name_for_user(from_user)} to "
        f"{display_name_for_user(to_user)} by {display_name_for_user(actor)} on {stamp}"
    )

    moved = 0
    with transaction.atomic():
        for kind, model in LEAD_MODELS.items():
            qs = model.objects.select_for_update().filter(assigned_user_id=from_user.pk)
            if wanted is not None:
                ids = wanted.get(kind)
                if not ids:
                    continue
                qs = qs.filter(pk__in=ids)
            for lead in qs:
                lead_status = _landing_status(lead) if kind == "landing" else (lead.status or "untouched")
                if wanted is None and open_only and not is_open_status(lead_status):
                    continue
                lead.assigned_user = to_user
                update_fields = ["assigned_user"]
                if hasattr(lead, "updated_at"):
                    update_fields.append("updated_at")
                if hasattr(lead, "raw_payload"):
                    payload = dict(lead.raw_payload) if isinstance(lead.raw_payload, dict) else {}
                    payload["crm_last_assigner_id"] = int(actor.pk)
                    payload["crm_transferred_from_id"] = int(from_user.pk)
                    lead.raw_payload = payload
                    update_fields.append("raw_payload")
                lead.save(update_fields=update_fields)
                UnifiedLeadNote.objects.create(
                    lead_id=f"{kind}_{lead.pk}", content=note_text, status=lead_status
                )
                moved += 1
    return moved
