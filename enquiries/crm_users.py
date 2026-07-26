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
    CRM handlers whose territory covers the lead's state/city.
    City-restricted users (e.g. Kerala districts) are listed first when city matches.
    National (unscoped) users are excluded.
    """
    from accounts.crm_zones import (
        city_match_variants,
        scope_city_names_for_user,
        scope_state_codes_for_user,
    )

    code = resolve_lead_state_code(state, city)
    if not code:
        return []

    lead_city = (city or "").strip()
    lead_city_keys = {v.casefold() for v in city_match_variants(lead_city)} if lead_city else set()

    city_specific: list[User] = []
    state_scoped: list[User] = []

    for user in crm_users_queryset():
        codes = scope_state_codes_for_user(user)
        if not codes or code not in codes:
            continue

        user_cities = scope_city_names_for_user(user)
        if user_cities is None:
            state_scoped.append(user)
            continue

        if not lead_city:
            # Lead has no city — include city-scoped users for this state
            city_specific.append(user)
            continue

        matched = False
        for c in user_cities:
            for variant in city_match_variants(c):
                if variant.casefold() in lead_city_keys or variant.casefold() == lead_city.casefold():
                    matched = True
                    break
            if matched:
                break
        if matched:
            city_specific.append(user)

    # Prefer narrower territories when assigning (fewer states = more specific).
    city_specific.sort(key=lambda u: u.id)
    state_scoped.sort(
        key=lambda u: (len(scope_state_codes_for_user(u) or []), u.id)
    )
    return city_specific + state_scoped


def suggest_assignee_for_geo(state: str | None = None, city: str | None = None) -> User | None:
    """Best default assignee: prefer city-matched user, else state-level handler."""
    matches = crm_users_matching_geo(state, city)
    return matches[0] if matches else None


def emails_for_geo_handlers(state: str | None = None, city: str | None = None) -> list[str]:
    """Unique CRM emails that should be notified for a lead in this territory."""
    seen: set[str] = set()
    out: list[str] = []
    for user in crm_users_matching_geo(state, city):
        email = (user.email or "").strip()
        if not email:
            continue
        key = email.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(email)
    return out


def _user_api_dict(user: User) -> dict:
    return {
        "id": user.id,
        "label": display_name_for_user(user),
        "fullName": display_name_for_user(user),
        "email": user.email,
        "crmZone": (getattr(user, "crm_zone", None) or "").strip().upper() or None,
        "crmRegion": (getattr(user, "crm_region", None) or "").strip().upper() or None,
        "crmStates": (getattr(user, "crm_states", None) or "").strip() or None,
        "crmCities": (getattr(user, "crm_cities", None) or "").strip() or None,
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
