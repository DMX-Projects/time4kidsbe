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
    "SOUTH_R1": ("AP", "TG", "KA"),
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

# Zonal Manager territories (TKPL) — merged with User.crm_states when set.
ZONAL_MANAGER_SCOPE_CODES: dict[str, tuple[str, ...]] = {
    "tejbal@timekidspreschools.com": ("AP", "TG", "KA"),
    "gaurav@timekidspreschools.com": ("TN", "KL", "MH"),
    "jyoti.mishra@timekidspreschools.com": ("BR", "CT", "OR", "WB"),
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
    Uses crm_states when set; else region; else zone.
    """
    user = _authenticated_user(request)
    if not user:
        return None
    return scope_state_codes_for_user(user)


def request_scope_cities(request) -> list[str] | None:
    """Logged-in CRM user's city list, or None if not city-restricted."""
    return scope_city_names_for_user(_authenticated_user(request))


def resolve_scope_cities(request, scope_user_id: str | None = None) -> list[str] | None:
    """
    Effective city list for geo dropdowns / lead filters.
    Intersects viewer cities with filter-user cities when both are set.
    None = not city-restricted.
    """
    if scope_user_id:
        from enquiries.crm_users import sanitize_crm_scope_user_id

        scope_user_id = sanitize_crm_scope_user_id(scope_user_id)

    viewer_cities = request_scope_cities(request)

    target_cities = None
    raw = (scope_user_id or "").strip().lower()
    if raw and raw not in ("unassigned", "all"):
        try:
            from accounts.models import User

            target = User.objects.filter(pk=int(raw), is_active=True).first()
            target_cities = scope_city_names_for_user(target)
        except (TypeError, ValueError):
            target_cities = None

    if viewer_cities is None and target_cities is None:
        return None
    if viewer_cities is None:
        return list(target_cities or [])
    if target_cities is None:
        return list(viewer_cities)
    allowed = {c.casefold() for c in viewer_cities}
    return [c for c in target_cities if c.casefold() in allowed]


def request_effective_scope_cities(request) -> list[str] | None:
    user_filter = _request_filter_user_id(request)
    if user_filter and user_filter not in ("unassigned", "none", "null", "all"):
        return resolve_scope_cities(request, user_filter)
    return request_scope_cities(request)


def parse_crm_states(raw: str | None) -> list[str]:
    """Parse comma-separated state codes/names from User.crm_states."""
    codes: list[str] = []
    seen: set[str] = set()
    for part in (raw or "").split(","):
        s = part.strip()
        if not s:
            continue
        code = state_to_code(s) or (s.upper() if len(s) <= 3 else None)
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


def parse_crm_cities(raw: str | None) -> list[str]:
    """Parse comma-separated city/district names from User.crm_cities."""
    cities: list[str] = []
    seen: set[str] = set()
    for part in (raw or "").split(","):
        name = part.strip()
        if not name:
            continue
        key = name.casefold()
        if key not in seen:
            seen.add(key)
            cities.append(name)
    return cities


def scope_city_names_for_user(user) -> list[str] | None:
    """
    Explicit city list for a CRM user, or None if not city-restricted.
    Empty list means city-restricted with no cities configured.
    """
    if not user:
        return None
    raw = (getattr(user, "crm_cities", None) or "").strip()
    if not raw:
        return None
    return parse_crm_cities(raw)


def scope_state_codes_for_user(user) -> list[str] | None:
    """
    Geographic scope for a CRM user account.
    None = national / unrestricted (no zone, region, or crm_states set).
    """
    if not user:
        return None
    email = (getattr(user, "email", "") or "").strip().lower()
    zonal_codes = list(ZONAL_MANAGER_SCOPE_CODES.get(email, ()))
    explicit = parse_crm_states(getattr(user, "crm_states", None))
    if zonal_codes or explicit:
        merged: list[str] = []
        seen: set[str] = set()
        for code in zonal_codes + (explicit or []):
            if code not in seen:
                seen.add(code)
                merged.append(code)
        if merged:
            return merged
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
    if scope_user_id:
        from enquiries.crm_users import sanitize_crm_scope_user_id

        scope_user_id = sanitize_crm_scope_user_id(scope_user_id)

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
    """``userId`` query param from dashboard filters (assignable handler id or unassigned)."""
    if request is None:
        return None
    params = getattr(request, "query_params", None) or getattr(request, "GET", {})
    raw = (params.get("userId") or "").strip()
    if not raw:
        return None
    from enquiries.crm_users import sanitize_crm_filter_user_id

    return sanitize_crm_filter_user_id(raw)


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


def city_match_variants(city: str) -> list[str]:
    """Return known spelling variants for a city/district name."""
    name = (city or "").strip()
    if not name:
        return []
    aliases = {
        "alappuzha": ("Alappuzha", "Alleppey"),
        "alleppey": ("Alappuzha", "Alleppey"),
        "kasaragod": ("Kasaragod", "Kasargod"),
        "kasargod": ("Kasaragod", "Kasargod"),
        "trivandrum": ("Trivandrum", "Thiruvananthapuram"),
        "thiruvananthapuram": ("Trivandrum", "Thiruvananthapuram"),
        "kozhikode": ("Kozhikode", "Calicut"),
        "cannanore": ("Kannur", "Cannanore"),
        "kannur": ("Kannur", "Cannanore"),
        "kolkata": ("Kolkata", "Calcutta"),
        "calcutta": ("Kolkata", "Calcutta"),
        "howrah": ("Howrah", "Haora"),
        "haora": ("Howrah", "Haora"),
        "hooghly": ("Hooghly", "HugliChunchura", "Hugli-Chinsurah"),
        "siliguri": ("Siliguri", "Shiliguri"),
        "shiliguri": ("Siliguri", "Shiliguri"),
        "darjeeling": ("Darjeeling", "Darjiling"),
        "khurda": ("Khurda", "Khordha"),
        "khordha": ("Khurda", "Khordha"),
        "berhampur": ("Berhampur", "Bhermpur", "Brahmapur", "Berhampore"),
        "bhermpur": ("Berhampur", "Bhermpur", "Brahmapur", "Berhampore"),
        "brahmapur": ("Berhampur", "Bhermpur", "Brahmapur", "Berhampore"),
        "bhubaneswar": ("Bhubaneswar", "Bhuneswar"),
        "bhuneswar": ("Bhubaneswar", "Bhuneswar"),
        "cuttack": ("Cuttack", "Cuttak", "Kataka"),
        "cuttak": ("Cuttack", "Cuttak", "Kataka"),
        "rourkela": ("Rourkela", "Raurkela", "Rorkela"),
        "raurkela": ("Rourkela", "Raurkela", "Rorkela"),
        "rorkela": ("Rourkela", "Raurkela", "Rorkela"),
    }
    variants = aliases.get(name.casefold())
    if variants:
        return list(variants)
    return [name, name.title()]


def _city_field_q(field: str, cities: list[str]) -> Q:
    q = Q()
    for city in cities:
        for variant in city_match_variants(city):
            q |= Q(**{f"{field}__iexact": variant})
    return q


def filter_enquiry_qs_by_zone(qs, request):
    codes = request_effective_scope_codes(request)
    cities = request_effective_scope_cities(request)
    if codes is None and cities is None:
        return qs
    from franchises.models import Franchise
    from franchises.franchise_geo import filter_queryset_by_state

    city_names: set[str] = set()
    if cities is not None:
        for city in cities:
            city_names.update(city_match_variants(city))
    elif codes is not None:
        for code in codes:
            for f in filter_queryset_by_state(Franchise.objects.filter(is_active=True), code):
                for raw in (getattr(f, "cityname", None), getattr(f, "city", None)):
                    name = (raw or "").strip()
                    if name:
                        city_names.add(name)
                        city_names.add(name.title())

    zone_q = Q()
    if codes is not None:
        zone_q = _state_field_q_for_codes("franchise__state", codes) | _state_field_q_for_codes(
            "franchise__statename", codes
        )
    if city_names:
        city_q = Q()
        for city in city_names:
            city_q |= Q(city__iexact=city)
        if codes is not None:
            zone_q = zone_q | (Q(franchise__isnull=True) & city_q)
            if cities is not None:
                zone_q = zone_q & city_q
        else:
            zone_q = city_q
    elif codes is not None:
        zone_q |= Q(pk__in=[])
    return qs.filter(zone_q)


def filter_franchise_enquiry_qs_by_zone(qs, request):
    codes = request_effective_scope_codes(request)
    cities = request_effective_scope_cities(request)
    if codes is None and cities is None:
        return qs
    zone_q = Q()
    if codes is not None:
        zone_q = (
            _state_field_q_for_codes("state", codes)
            | _state_field_q_for_codes("franchise__state", codes)
            | _state_field_q_for_codes("franchise__statename", codes)
        )
    if cities is not None:
        city_q = _city_field_q("city", cities)
        zone_q = zone_q & city_q if codes is not None else city_q
    return qs.filter(zone_q)


def filter_crm_lead_qs_by_zone(qs, request):
    codes = request_effective_scope_codes(request)
    cities = request_effective_scope_cities(request)
    if codes is None and cities is None:
        return qs
    from franchises.models import Franchise
    from franchises.franchise_geo import filter_queryset_by_state

    city_names: set[str] = set()
    centre_names: set[str] = set()
    if cities is not None:
        for city in cities:
            city_names.update(city_match_variants(city))
    elif codes is not None:
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

    zone_q = Q()
    if codes is not None:
        zone_q = _state_field_q_for_codes("state", codes)
    if city_names:
        cq = Q()
        for city in city_names:
            cq |= Q(city__iexact=city)
        if codes is not None and cities is not None:
            zone_q = zone_q & cq
        elif codes is not None:
            zone_q = zone_q | cq
        else:
            zone_q = cq
    if centre_names and cities is None:
        zc = Q()
        for name in centre_names:
            zc |= Q(preferred_centre_location__iexact=name)
        zone_q = zone_q | zc
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
