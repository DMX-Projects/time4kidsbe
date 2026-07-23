"""CRM user labels for reports — real names, no Super Admin, no 'CRM ' prefix."""

from __future__ import annotations

from accounts.models import User, UserRole


def crm_users_queryset():
    """Active CRM users excluding Super Admin (manager login, not a lead handler)."""
    return (
        User.objects.filter(role__iexact=UserRole.CRM.value, is_active=True)
        .exclude(email__iexact="admin@timekids.com")
        .exclude(full_name__icontains="Super Admin")
        .order_by("id")
    )


def display_name_for_user(user: User) -> str:
    name = (user.full_name or "").strip()
    if name.lower().startswith("crm "):
        name = name[4:].strip()
    if name:
        return name
    email = (user.email or "").strip()
    if email:
        local = email.split("@")[0]
        if local.lower().startswith("crm."):
            local = local[4:]
        return local.replace(".", " ").strip() or email
    return f"User {user.id}"


def crm_user_label_map() -> dict[int, str]:
    """Map user id → display name."""
    return {user.id: display_name_for_user(user) for user in crm_users_queryset()}


def label_for_crm_user(user_id: int | None) -> str | None:
    if not user_id:
        return None
    user = User.objects.filter(pk=int(user_id)).first()
    if not user:
        return None
    return display_name_for_user(user)


def resolve_lead_state_code(state: str | None = None, city: str | None = None) -> str | None:
    """Resolve a lead's state code from state text and/or city name."""
    from franchises.franchise_geo import filter_queryset_by_city, state_to_code

    code = state_to_code(state)
    if code:
        return code

    city_name = (city or "").strip()
    if not city_name:
        return None

    from franchises.models import Franchise, FranchiseLocation

    loc = (
        FranchiseLocation.objects.filter(is_active=True, city_name__iexact=city_name)
        .exclude(state__isnull=True)
        .exclude(state="")
        .first()
    )
    if loc:
        code = state_to_code(loc.state)
        if code:
            return code

    franchise = filter_queryset_by_city(Franchise.objects.filter(is_active=True), city_name).first()
    if franchise:
        return state_to_code(
            getattr(franchise, "statename", None) or getattr(franchise, "state", None)
        )
    return None


def crm_users_matching_geo(state: str | None = None, city: str | None = None) -> list[User]:
    """
    CRM handlers whose zone/region covers the lead's state (city used to infer state).
    Prefers regional users; falls back to zonal users. National (unscoped) users are excluded.
    """
    from accounts.crm_zones import scope_state_codes_for_user

    code = resolve_lead_state_code(state, city)
    if not code:
        return []

    regional: list[User] = []
    zonal: list[User] = []
    for user in crm_users_queryset():
        codes = scope_state_codes_for_user(user)
        if not codes or code not in codes:
            continue
        if (getattr(user, "crm_region", None) or "").strip():
            regional.append(user)
        elif (getattr(user, "crm_zone", None) or "").strip():
            zonal.append(user)
    return regional if regional else zonal


def suggest_assignee_for_geo(state: str | None = None, city: str | None = None) -> User | None:
    """Best default assignee for a lead's city/state territory."""
    matches = crm_users_matching_geo(state, city)
    return matches[0] if matches else None


def _user_api_dict(user: User) -> dict:
    return {
        "id": user.id,
        "label": display_name_for_user(user),
        "fullName": display_name_for_user(user),
        "email": user.email,
        "crmZone": (getattr(user, "crm_zone", None) or "").strip().upper() or None,
        "crmRegion": (getattr(user, "crm_region", None) or "").strip().upper() or None,
    }


def list_crm_users_for_api(state: str | None = None, city: str | None = None) -> list[dict]:
    """
    List CRM users for filters / assignment.
    When state or city is provided, only return users covering that territory.
    """
    if (state or "").strip() or (city or "").strip():
        users = crm_users_matching_geo(state, city)
    else:
        users = list(crm_users_queryset())
    return [_user_api_dict(user) for user in users]


def assigned_user_payload(
    user,
    *,
    state: str | None = None,
    city: str | None = None,
    include_suggestion: bool = False,
) -> dict:
    payload = {
        "assignedUserId": user.id if user else None,
        "assignedUserLabel": display_name_for_user(user) if user else None,
    }
    if include_suggestion and not user:
        suggested = suggest_assignee_for_geo(state, city)
        payload["suggestedAssignedUserId"] = suggested.id if suggested else None
        payload["suggestedAssignedUserLabel"] = (
            display_name_for_user(suggested) if suggested else None
        )
    return payload
