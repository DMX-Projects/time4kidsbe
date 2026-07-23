"""CRM zone + region helpers — scopes CRM users to states/cities/centres."""

from __future__ import annotations

from django.db.models import Q

from franchises.franchise_geo import STATE_CODE_TO_NAME, expand_state_filter, state_to_code, state_to_display


class CrmZone:
    EAST = "EAST"
    WEST = "WEST"
    NORTH = "NORTH"
    SOUTH = "SOUTH"
    ALL = ("EAST", "WEST", "NORTH", "SOUTH")


# Full zone → states
ZONE_STATE_CODES: dict[str, tuple[str, ...]] = {
    CrmZone.NORTH: ("DL", "HR", "HP", "JK", "LA", "PB", "RJ", "UP", "UT", "CH"),
    CrmZone.SOUTH: ("AP", "KA", "KL", "TN", "TG", "PY", "LD", "AN"),
    CrmZone.EAST: ("AS", "BR", "JH", "OR", "SK", "WB", "AR", "MN", "ML", "MZ", "NL", "TR"),
    CrmZone.WEST: ("GA", "GJ", "MH", "MP", "CT", "DN", "DD"),
}


# 2 regions per zone — each region gets 1–2 states (max 3).
REGION_STATE_CODES: dict[str, tuple[str, ...]] = {
    # North
    "NORTH_R1": ("DL", "HR"),
    "NORTH_R2": ("UP", "PB"),
    # South
    "SOUTH_R1": ("AP", "TG"),
    "SOUTH_R2": ("TN", "KL"),
    # East
    "EAST_R1": ("WB", "OR"),
    "EAST_R2": ("BR", "JH"),
    # West
    "WEST_R1": ("MH",),
    "WEST_R2": ("GJ", "MP"),
}

REGION_PARENT_ZONE: dict[str, str] = {
    "NORTH_R1": CrmZone.NORTH,
    "NORTH_R2": CrmZone.NORTH,
    "SOUTH_R1": CrmZone.SOUTH,
    "SOUTH_R2": CrmZone.SOUTH,
    "EAST_R1": CrmZone.EAST,
    "EAST_R2": CrmZone.EAST,
    "WEST_R1": CrmZone.WEST,
    "WEST_R2": CrmZone.WEST,
}

REGION_LABELS: dict[str, str] = {
    "NORTH_R1": "North Region 1",
    "NORTH_R2": "North Region 2",
    "SOUTH_R1": "South Region 1",
    "SOUTH_R2": "South Region 2",
    "EAST_R1": "East Region 1",
    "EAST_R2": "East Region 2",
    "WEST_R1": "West Region 1",
    "WEST_R2": "West Region 2",
}


def normalize_zone(value: str | None) -> str | None:
    zone = (value or "").strip().upper()
    if zone in ZONE_STATE_CODES:
        return zone
    return None


def normalize_region(value: str | None) -> str | None:
    region = (value or "").strip().upper().replace("-", "_").replace(" ", "_")
    if region in REGION_STATE_CODES:
        return region
    return None


def zone_state_codes(zone: str | None) -> list[str]:
    z = normalize_zone(zone)
    if not z:
        return []
    return list(ZONE_STATE_CODES[z])


def region_state_codes(region: str | None) -> list[str]:
    r = normalize_region(region)
    if not r:
        return []
    return list(REGION_STATE_CODES[r])


def _authenticated_user(request):
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return user
    forced = getattr(request, "_force_auth_user", None)
    if forced is not None and getattr(forced, "is_authenticated", False):
        return forced
    return None


def request_crm_zone(request) -> str | None:
    user = _authenticated_user(request)
    if not user:
        return None
    return normalize_zone(getattr(user, "crm_zone", None))


def request_crm_region(request) -> str | None:
    user = _authenticated_user(request)
    if not user:
        return None
    return normalize_region(getattr(user, "crm_region", None))


def request_scope_state_codes(request) -> list[str] | None:
    """
    Effective CRM geographic scope as state codes.
    None = national (unrestricted).
    Regional users get region states; zonal users get full zone states.
    """
    region = request_crm_region(request)
    if region:
        return region_state_codes(region)
    zone = request_crm_zone(request)
    if zone:
        return zone_state_codes(zone)
    return None


def scope_state_codes_for_user(user) -> list[str] | None:
    """
    Geographic scope for a CRM user account.
    None = national / unrestricted (no zone or region set).
    """
    if not user:
        return None
    region = normalize_region(getattr(user, "crm_region", None))
    if region:
        return region_state_codes(region)
    zone = normalize_zone(getattr(user, "crm_zone", None))
    if zone:
        return zone_state_codes(zone)
    return None


def resolve_scope_state_codes(request, scope_user_id: str | None = None) -> list[str] | None:
    """
    State codes for geo dropdowns (states/cities).
    Always respects the logged-in CRM user's scope; optionally narrows further
    to a selected filter user's zone/region (``userId`` on the request).
    None = unrestricted.
    """
    viewer_codes = request_scope_state_codes(request)

    target_codes = None
    raw = (scope_user_id or "").strip().lower()
    if raw and raw not in ("unassigned", "all"):
        try:
            from accounts.models import User

            target = User.objects.filter(pk=int(raw), is_active=True).first()
            target_codes = scope_state_codes_for_user(target)
        except (TypeError, ValueError):
            target_codes = None

    if viewer_codes is None and target_codes is None:
        return None
    if viewer_codes is None:
        return list(target_codes or [])
    if target_codes is None:
        return list(viewer_codes)
    allowed = set(viewer_codes)
    intersected = [c for c in target_codes if c in allowed]
    return intersected if intersected else list(viewer_codes)


def _request_filter_user_id(request) -> str | None:
    """``userId`` query param from dashboard filters (numeric id, ``unassigned``, or empty)."""
    if request is None:
        return None
    params = getattr(request, "query_params", None) or getattr(request, "GET", {})
    raw = (params.get("userId") or "").strip().lower()
    return raw or None


def request_effective_scope_codes(request) -> list[str] | None:
    """
    Geographic scope for lead queries.
    When a filter user is selected, narrow to that user's zone/region (intersected with viewer).
    Otherwise use the logged-in CRM user's scope.
    """
    user_filter = _request_filter_user_id(request)
    if user_filter and user_filter not in ("unassigned", "none", "null", "all"):
        return resolve_scope_state_codes(request, user_filter)
    return request_scope_state_codes(request)

def scope_match_values(codes: list[str] | None) -> list[str]:
    if not codes:
        return []
    values: set[str] = set()
    for code in codes:
        values.update(expand_state_filter(code))
        name = STATE_CODE_TO_NAME.get(code)
        if name:
            values.add(name)
            values.add(name.title())
    return [v for v in values if v]


def scope_display_state_names(codes: list[str] | None) -> list[str]:
    if not codes:
        return []
    return sorted(
        {STATE_CODE_TO_NAME[c] for c in codes if c in STATE_CODE_TO_NAME},
        key=str.casefold,
    )


def zone_match_values(zone: str | None) -> list[str]:
    return scope_match_values(zone_state_codes(zone))


def zone_display_state_names(zone: str | None) -> list[str]:
    return scope_display_state_names(zone_state_codes(zone))


def scope_city_names(codes: list[str] | None, state_param: str | None = None) -> list[str]:
    """Full city list for a set of state codes (Franchise + FranchiseLocation)."""
    if not codes:
        return []

    from franchises.models import Franchise, FranchiseLocation
    from franchises.franchise_geo import filter_queryset_by_state

    allowed = set(codes)
    if state_param and state_param.strip():
        selected: list[str] = []
        for part in state_param.split(","):
            s = part.strip()
            if not s:
                continue
            code = state_to_code(s)
            if code and code in allowed:
                selected.append(code)
        codes = selected or list(allowed)

    cities: set[str] = set()
    for code in codes:
        for name in (
            FranchiseLocation.objects.filter(state=code, is_active=True)
            .exclude(city_name__isnull=True)
            .exclude(city_name="")
            .values_list("city_name", flat=True)
        ):
            cleaned = (name or "").strip().title()
            if cleaned:
                cities.add(cleaned)
        for f in filter_queryset_by_state(Franchise.objects.all(), code):
            for raw in (getattr(f, "cityname", None), getattr(f, "city", None)):
                cleaned = (raw or "").strip().title()
                if cleaned:
                    cities.add(cleaned)

    return sorted(cities, key=str.casefold)


def zone_city_names(zone: str | None, state_param: str | None = None) -> list[str]:
    return scope_city_names(zone_state_codes(zone), state_param)


def state_in_codes(state_raw: str | None, codes: list[str] | None) -> bool:
    if not codes:
        return True
    code = state_to_code(state_raw)
    if code:
        return code in codes
    display = state_to_display(state_raw)
    return display.casefold() in {n.casefold() for n in scope_display_state_names(codes)}


def state_in_zone(state_raw: str | None, zone: str | None) -> bool:
    return state_in_codes(state_raw, zone_state_codes(zone) or None)


def clamp_requested_states(request, state_param: str | None) -> str | None:
    """If user is scoped, drop any requested states outside their region/zone."""
    codes = request_effective_scope_codes(request)
    raw = (state_param or "").strip()
    if codes is None:
        return raw or None
    allowed = scope_match_values(codes)
    allowed_cf = {a.casefold() for a in allowed}
    default_names = ",".join(scope_display_state_names(codes))
    if not raw:
        return default_names
    kept: list[str] = []
    for part in raw.split(","):
        s = part.strip()
        if not s:
            continue
        if s.casefold() in allowed_cf or state_in_codes(s, codes):
            kept.append(state_to_display(s) or s)
    if not kept:
        return default_names
    return ",".join(kept)


def _state_field_q_for_codes(field: str, codes: list[str]) -> Q:
    q = Q()
    for value in scope_match_values(codes):
        q |= Q(**{f"{field}__iexact": value})
    return q


def filter_enquiry_qs_by_zone(qs, request):
    codes = request_effective_scope_codes(request)
    if codes is None:
        return qs
    from franchises.models import Franchise
    from franchises.franchise_geo import filter_queryset_by_state

    city_names: set[str] = set()
    for code in codes:
        for f in filter_queryset_by_state(Franchise.objects.filter(is_active=True), code):
            for raw in (getattr(f, "cityname", None), getattr(f, "city", None)):
                name = (raw or "").strip()
                if name:
                    city_names.add(name)
                    city_names.add(name.title())

    zone_q = _state_field_q_for_codes("franchise__state", codes) | _state_field_q_for_codes(
        "franchise__statename", codes
    )
    if city_names:
        city_q = Q()
        for city in city_names:
            city_q |= Q(city__iexact=city)
        zone_q |= Q(franchise__isnull=True) & city_q
    else:
        zone_q |= Q(pk__in=[])
    return qs.filter(zone_q)


def filter_franchise_enquiry_qs_by_zone(qs, request):
    codes = request_effective_scope_codes(request)
    if codes is None:
        return qs
    zone_q = (
        _state_field_q_for_codes("state", codes)
        | _state_field_q_for_codes("franchise__state", codes)
        | _state_field_q_for_codes("franchise__statename", codes)
    )
    return qs.filter(zone_q)


def filter_crm_lead_qs_by_zone(qs, request):
    codes = request_effective_scope_codes(request)
    if codes is None:
        return qs
    from franchises.models import Franchise
    from franchises.franchise_geo import filter_queryset_by_state

    city_names: set[str] = set()
    centre_names: set[str] = set()
    for code in codes:
        for f in filter_queryset_by_state(Franchise.objects.filter(is_active=True), code):
            for raw in (getattr(f, "cityname", None), getattr(f, "city", None)):
                name = (raw or "").strip()
                if name:
                    city_names.add(name)
                    city_names.add(name.title())
            fname = (f.name or "").strip()
            if fname:
                centre_names.add(fname)

    zone_q = _state_field_q_for_codes("state", codes)
    if city_names:
        cq = Q()
        for city in city_names:
            cq |= Q(city__iexact=city)
        zone_q |= cq
    if centre_names:
        zc = Q()
        for name in centre_names:
            zc |= Q(preferred_centre_location__iexact=name)
        zone_q |= zc
    return qs.filter(zone_q)


def filter_franchise_qs_by_zone(qs, request):
    codes = request_effective_scope_codes(request)
    if codes is None:
        return qs
    from franchises.franchise_geo import filter_queryset_by_state

    out = qs.none()
    for code in codes:
        out = out | filter_queryset_by_state(qs, code)
    return out.distinct()


def lead_dict_in_zone(lead: dict, zone: str | None) -> bool:
    if not normalize_zone(zone):
        return True
    return state_in_zone(lead.get("state"), zone)
