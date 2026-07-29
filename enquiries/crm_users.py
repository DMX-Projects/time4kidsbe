"""CRM user labels for reports — real names, no Super Admin, no 'CRM ' prefix."""

from __future__ import annotations

from accounts.models import User, UserRole

# TKPL list — Zonal Managers who may reassign leads to territory users.
ZONAL_MANAGER_ASSIGN_EMAILS = frozenset(
    {
        "tejbal@timekidspreschools.com",
        "gaurav@timekidspreschools.com",
        "jyoti.mishra@timekidspreschools.com",
    }
)

# National CRM super admins who may also reassign leads.
CRM_SUPER_ADMIN_ASSIGN_EMAILS = frozenset(
    {
        "admin@timekids.com",
        "jayesh@time4education.com",
        "bethleena@timekidspreschools.com",
    }
)

CRM_LEAD_ASSIGNER_EMAILS = ZONAL_MANAGER_ASSIGN_EMAILS | CRM_SUPER_ADMIN_ASSIGN_EMAILS

# TKPL designations that may receive leads (not Zonal Manager / Super Admin).
# Regional Manager, Manager, Dy Manager, Assistant Manager only.
CRM_ASSIGNABLE_HANDLER_EMAILS = frozenset(
    {
        # Dy Manager
        "saikishore@timekidspreschools.com",
        # Assistant Manager
        "harshit@timekidspreschools.com",
        "sivaraman@timekidspreschools.com",
        "anoopkunjan@timekidspreschools.com",
        # Regional Manager
        "sujee@timekidspreschools.com",
        "joejoseph@timekidspreschools.com",
        "vivek@timekidspreschools.com",
        # Manager
        "thimmesh.k@timekidspreschools.com",
        "jayaraj@timekidspreschools.com",
        "satishmenon@timekidspreschools.com",
        "deepaknikam@timekidspreschools.com",
    }
)

CRM_ASSIGNABLE_DESIGNATIONS = (
    "Regional Manager",
    "Manager",
    "Dy Manager",
    "Assistant Manager",
)

# TKPL Franchise sheet — handlers under each Zonal Manager (Select User / assign for franchise leads).
ZONAL_MANAGER_FRANCHISE_TEAM_EMAILS: dict[str, frozenset[str]] = {
    "tejbal@timekidspreschools.com": frozenset(
        {
            "saikishore@timekidspreschools.com",  # Dy Manager — AP/TS
            "harshit@timekidspreschools.com",  # Assistant Manager — AP/TS
            "sujee@timekidspreschools.com",  # Regional Manager — Karnataka
        }
    ),
    "gaurav@timekidspreschools.com": frozenset(
        {
            "jayaraj@timekidspreschools.com",  # Manager — Tamil Nadu
            "joejoseph@timekidspreschools.com",  # Regional Manager — Kerala
            "satishmenon@timekidspreschools.com",  # Manager — Kerala
            "vivek@timekidspreschools.com",  # Regional Manager — Kerala
            "deepaknikam@timekidspreschools.com",  # Manager — Maharashtra
        }
    ),
    # Bihar / Chhattisgarh / Orissa / West Bengal — no franchise handlers on sheet; full handler list.
    "jyoti.mishra@timekidspreschools.com": frozenset(),
}

# TKPL Admission sheet — handlers under each Zonal Manager (Select User / assign for admission leads).
ZONAL_MANAGER_ADMISSION_TEAM_EMAILS: dict[str, frozenset[str]] = {
    "tejbal@timekidspreschools.com": frozenset(
        {
            "saikishore@timekidspreschools.com",  # Dy Manager — AP/TS
            "harshit@timekidspreschools.com",  # Assistant Manager — AP/TS
            "sujee@timekidspreschools.com",  # Regional Manager — Karnataka
            "thimmesh.k@timekidspreschools.com",  # Manager — Karnataka (admission sheet)
        }
    ),
    "gaurav@timekidspreschools.com": frozenset(
        {
            "jayaraj@timekidspreschools.com",  # Manager — Tamil Nadu
            "sivaraman@timekidspreschools.com",  # Assistant Manager — Tamil Nadu
            "joejoseph@timekidspreschools.com",  # Regional Manager — Kerala
            "satishmenon@timekidspreschools.com",  # Manager — Kerala
            "anoopkunjan@timekidspreschools.com",  # Assistant Manager — Kerala
            "vivek@timekidspreschools.com",  # Regional Manager — Kerala
            "deepaknikam@timekidspreschools.com",  # Manager — Maharashtra
        }
    ),
    # Bihar / Chhattisgarh / Orissa / West Bengal — no admission handlers on sheet; full handler list.
    "jyoti.mishra@timekidspreschools.com": frozenset(),
}


def user_can_assign_crm_leads(user) -> bool:
    """True for Zonal Managers and national CRM Super Admins."""
    if user is None:
        return False
    email = str(getattr(user, "email", "") or "").strip().lower()
    return email in CRM_LEAD_ASSIGNER_EMAILS


def is_assignable_handler_user(user) -> bool:
    """True for RM / Manager / Dy Manager / Assistant Manager (not Zonal Manager)."""
    if user is None or not getattr(user, "is_active", False):
        return False
    email = str(getattr(user, "email", "") or "").strip().lower()
    return email in CRM_ASSIGNABLE_HANDLER_EMAILS


def filter_leads_for_crm_viewer(qs, request):
    """
    Territory managers only see leads explicitly assigned to their own login.
    Zonal Managers and Super Admins retain their normal geographic/all-lead view.
    """
    viewer = _viewer_from_request(request)
    if is_assignable_handler_user(viewer):
        return qs.filter(assigned_user_id=viewer.pk)
    return qs


def _filter_assignable_handlers(users: list[User]) -> list[User]:
    return [u for u in users if is_assignable_handler_user(u)]


def all_assignable_handler_users() -> list[User]:
    """All TKPL RM / Manager / Dy Manager / Assistant Manager accounts."""
    return _filter_assignable_handlers(list(crm_users_queryset()))


def zonal_franchise_uses_full_handler_list(viewer) -> bool:
    """Zonal Manager with no franchise team — show every assignable handler."""
    if not viewer:
        return False
    email = str(getattr(viewer, "email", "") or "").strip().lower()
    team = ZONAL_MANAGER_FRANCHISE_TEAM_EMAILS.get(email)
    return team is not None and len(team) == 0


def zonal_admission_uses_full_handler_list(viewer) -> bool:
    """Zonal Manager with no admission team — show every assignable handler."""
    if not viewer:
        return False
    email = str(getattr(viewer, "email", "") or "").strip().lower()
    team = ZONAL_MANAGER_ADMISSION_TEAM_EMAILS.get(email)
    return team is not None and len(team) == 0


def _viewer_from_request(request) -> User | None:
    if request is None:
        return None
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return user
    forced = getattr(request, "_force_auth_user", None)
    if forced is not None and getattr(forced, "is_authenticated", False):
        return forced
    return None


def normalize_crm_pipeline(raw: str | None) -> str | None:
    """``franchise`` | ``admission`` | None (geo-only, no zonal team sheet)."""
    value = (raw or "").strip().lower().replace("-", "_")
    if not value:
        return None
    if value in ("franchise", "campaign", "websiteleads", "paidcampaign", "franchise_all", "crm"):
        return "franchise"
    if value in ("admission", "landing", "contact", "centerpage", "enquiry"):
        return "admission"
    if value == "franchiseenquiry":
        return "franchise"
    return None


def zonal_manager_team_users(viewer, pipeline: str | None = None) -> list[User]:
    """Assignable handlers on the TKPL franchise/admission sheet for this Zonal Manager."""
    email = str(getattr(viewer, "email", "") or "").strip().lower()
    pipe = normalize_crm_pipeline(pipeline)
    if pipe == "franchise":
        team_emails = ZONAL_MANAGER_FRANCHISE_TEAM_EMAILS.get(email)
    elif pipe == "admission":
        team_emails = ZONAL_MANAGER_ADMISSION_TEAM_EMAILS.get(email)
    else:
        return []
    if not team_emails:
        return []
    return [
        user
        for user in crm_users_queryset()
        if (user.email or "").strip().lower() in team_emails
    ]


def _merge_user_lists(primary: list[User], extra: list[User]) -> list[User]:
    seen = {user.id for user in primary}
    merged = list(primary)
    for user in extra:
        if user.id not in seen:
            seen.add(user.id)
            merged.append(user)
    return merged


def _zonal_team_users_for_context(
    request,
    state_param: str | None = None,
    city_param: str | None = None,
    pipeline: str | None = None,
) -> list[User]:
    """Zonal manager's franchise/admission team — full team or narrowed to state/city filter."""
    viewer = _viewer_from_request(request)
    if not viewer:
        return []
    team = zonal_manager_team_users(viewer, pipeline)
    if not team:
        return []
    state_s = (state_param or "").strip()
    city_s = (city_param or "").strip()
    if not state_s and not city_s:
        return team
    geo_ids = {user.id for user in crm_users_matching_geo_filter(state_s or None, city_s or None)}
    return [user for user in team if user.id in geo_ids]


def sanitize_crm_filter_user_id(raw: str | None) -> str | None:
    """
    CRM dashboard ``userId`` query param.
    Returns empty → None, unassigned tokens, or assignable handler id string.
    Super admins / zonal managers / other CRM logins are rejected.
    """
    value = (raw or "").strip().lower()
    if not value:
        return None
    if value in ("unassigned", "none", "null", "all"):
        return value
    try:
        uid = int(value)
    except (TypeError, ValueError):
        return None
    user = User.objects.filter(pk=uid, role__iexact=UserRole.CRM.value, is_active=True).first()
    if not is_assignable_handler_user(user):
        return None
    return str(uid)


def sanitize_crm_scope_user_id(raw: str | None) -> str | None:
    """Geo API scope user — assignable territory handlers only."""
    cleaned = sanitize_crm_filter_user_id(raw)
    if not cleaned or cleaned in ("unassigned", "none", "null", "all"):
        return None
    return cleaned


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
    from collections import Counter

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

    # Prefer the majority state among active centres in this city.
    # Avoids one bad row (e.g. Coimbatore centre tagged Kerala) hijacking assignment.
    franchises = filter_queryset_by_city(Franchise.objects.filter(is_active=True), city_name)
    tallies: Counter[str] = Counter()
    for franchise in franchises.only("state", "statename")[:80]:
        raw = getattr(franchise, "statename", None) or getattr(franchise, "state", None)
        mapped = state_to_code(raw)
        if mapped:
            tallies[mapped] += 1
    if tallies:
        return tallies.most_common(1)[0][0]
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


def _parse_geo_csv(raw: str | None) -> list[str]:
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def crm_users_matching_geo_filter(
    state_param: str | None = None,
    city_param: str | None = None,
) -> list[User]:
    """Union of territory handlers for comma-separated state/city dashboard filters."""
    states = _parse_geo_csv(state_param)
    cities = _parse_geo_csv(city_param)
    if not states and not cities:
        return []

    seen_ids: set[int] = set()
    matched: list[User] = []

    def _add(users: list[User]) -> None:
        for user in users:
            if user.id in seen_ids:
                continue
            seen_ids.add(user.id)
            matched.append(user)

    if cities:
        if states:
            for state in states:
                for city in cities:
                    _add(crm_users_matching_geo(state, city))
        else:
            for city in cities:
                _add(crm_users_matching_geo(None, city))
    else:
        for state in states:
            _add(crm_users_matching_geo(state, None))

    return matched


def crm_users_matching_request_scope(request, pipeline: str | None = None) -> list[User]:
    """Handlers whose territory overlaps the logged-in viewer's CRM scope."""
    from accounts.crm_zones import request_effective_scope_codes, scope_display_state_names

    pipe = normalize_crm_pipeline(pipeline)
    codes = request_effective_scope_codes(request)
    if codes is None:
        return list(crm_users_queryset())
    state_names = scope_display_state_names(codes)
    if not state_names:
        return zonal_manager_team_users(_viewer_from_request(request), pipe)
    geo_users = crm_users_matching_geo_filter(",".join(state_names), None)
    if pipe:
        team = zonal_manager_team_users(_viewer_from_request(request), pipe)
        return _merge_user_lists(geo_users, team)
    return geo_users


def _pipeline_handler_emails(pipeline: str | None) -> frozenset[str]:
    """Assignable handlers listed on the selected Franchise/Admission sheet."""
    pipe = normalize_crm_pipeline(pipeline)
    if pipe == "franchise":
        teams = ZONAL_MANAGER_FRANCHISE_TEAM_EMAILS.values()
    elif pipe == "admission":
        teams = ZONAL_MANAGER_ADMISSION_TEAM_EMAILS.values()
    else:
        return CRM_ASSIGNABLE_HANDLER_EMAILS
    return frozenset(email for team in teams for email in team)


def suggest_assignee_for_geo(
    state: str | None = None,
    city: str | None = None,
    *,
    pipeline: str | None = None,
) -> User | None:
    """
    Best city/state handler from the Franchise/Admission sheet for routing helpers.
    This function does not persist an assignment; only an explicit ZM action does.
    """
    matches = crm_users_matching_geo(state, city)
    if not matches:
        return None
    allowed_handlers = _pipeline_handler_emails(pipeline)
    for user in matches:
        email = (user.email or "").strip().lower()
        if email in allowed_handlers:
            return user
    # A territory with no manager on that pipeline's sheet falls back to its ZM.
    for user in matches:
        email = (user.email or "").strip().lower()
        if email in ZONAL_MANAGER_ASSIGN_EMAILS:
            return user
    return None


def resolve_new_lead_mail_recipients(
    state: str | None = None,
    city: str | None = None,
    *,
    preferred_to: str | None = None,
    lead_kind: str | None = None,
) -> tuple[list[str], list[str]]:
    """
    New-lead mail routing from the mapping sheets:

    - Unassigned lead To: covering Zonal Manager
    - Assigned lead To: explicit assignee
    - Cc: covering Zonal Manager(s) + Jayesh

    Territory managers are deliberately excluded until explicit assignment.

    Returns ``(to_emails, cc_emails)``.
    """
    jayesh = "jayesh@time4education.com"
    pipe = normalize_crm_pipeline(lead_kind)
    allowed_handlers = _pipeline_handler_emails(pipe)
    city_matches = crm_users_matching_geo(state, city)
    # Peers / ZMs for Cc: everyone covering the state (city ignored)
    state_matches = crm_users_matching_geo(state, None) if (state or "").strip() else city_matches

    def _collect(users: list[User]) -> tuple[list[str], list[str]]:
        managers: list[str] = []
        zonals: list[str] = []
        seen_m: set[str] = set()
        seen_z: set[str] = set()
        for user in users:
            email = (user.email or "").strip().lower()
            if not email:
                continue
            if email in allowed_handlers and email not in seen_m:
                seen_m.add(email)
                managers.append(email)
            if email in ZONAL_MANAGER_ASSIGN_EMAILS and email not in seen_z:
                seen_z.add(email)
                zonals.append(email)
            # Pink notify heads covering territory (e.g. Sujee for Karnataka)
            notify_for_pipeline = (
                getattr(user, "crm_notify_franchise", False)
                if pipe == "franchise"
                else getattr(user, "crm_notify_admission", False)
                if pipe == "admission"
                else (
                    getattr(user, "crm_notify_franchise", False)
                    or getattr(user, "crm_notify_admission", False)
                )
            )
            if (
                notify_for_pipeline
                and email not in seen_z
                and email not in seen_m
            ):
                seen_z.add(email)
                zonals.append(email)
        return managers, zonals

    city_managers, city_zonals = _collect(city_matches)
    state_managers, state_zonals = _collect(state_matches)

    preferred = (preferred_to or "").strip().lower()
    match_emails = {(u.email or "").strip().lower() for u in city_matches + state_matches}

    to_email = ""
    preferred_is_allowed = (
        preferred in allowed_handlers or preferred in ZONAL_MANAGER_ASSIGN_EMAILS
    )
    if preferred and preferred in match_emails and preferred_is_allowed:
        to_email = preferred
    elif city_zonals:
        to_email = city_zonals[0]
    elif state_zonals:
        to_email = state_zonals[0]

    if not to_email:
        return [jayesh], []

    cc: list[str] = []
    seen_cc = {to_email}

    def _add_cc(addr: str) -> None:
        key = (addr or "").strip().lower()
        if key and key not in seen_cc:
            seen_cc.add(key)
            cc.append(key)

    # Managers are not notified until a ZM/Super Admin explicitly assigns the lead.
    for addr in state_zonals:
        _add_cc(addr)
    _add_cc(jayesh)

    return [to_email], cc


def emails_for_geo_handlers(
    state: str | None = None,
    city: str | None = None,
    *,
    lead_kind: str | None = None,
) -> list[str]:
    """
    Unique CRM emails that should be notified for a lead in this territory.
    lead_kind: ``franchise`` | ``admission`` | None (any notify flag).
    """
    kind = (lead_kind or "").strip().lower()
    seen: set[str] = set()
    out: list[str] = []
    for user in crm_users_matching_geo(state, city):
        if kind in ("franchise", "franchiseenquiry", "campaign", "websiteleads", "paidcampaign"):
            if not getattr(user, "crm_notify_franchise", False):
                continue
        elif kind in ("admission", "landing", "enquiry"):
            if not getattr(user, "crm_notify_admission", False):
                continue
        else:
            # Fallback: either franchise or admission notify
            if not (
                getattr(user, "crm_notify_franchise", False)
                or getattr(user, "crm_notify_admission", False)
                or getattr(user, "crm_notify_leads", False)
            ):
                continue
        email = (user.email or "").strip()
        if not email:
            continue
        key = email.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(email)
    return out


def resolve_notify_lead_kind(obj=None, lead_source: str = "") -> str:
    """Map a lead object / source label to franchise | admission | other."""
    source = (lead_source or "").strip().lower()
    if obj is not None:
        model = type(obj).__name__.lower()
        if "franchise" in model:
            return "franchise"
        if model == "crmlead":
            return "franchise"  # campaign / website franchise pipeline
        if model in ("enquiry", "kidsenquiry"):
            et = (getattr(obj, "enquiry_type", None) or "").strip().upper()
            if et == "FRANCHISE":
                return "franchise"
            return "admission"
    if any(k in source for k in ("franchise", "campaign", "meta", "google", "website lead", "paid")):
        return "franchise"
    if any(k in source for k in ("admission", "landing", "contact")):
        return "admission"
    return "other"


def _user_api_dict(user: User) -> dict:
    return {
        "id": user.id,
        "label": display_name_for_user(user),
        "fullName": display_name_for_user(user),
        "email": user.email,
        "crmZone": (getattr(user, "crm_zone", None) or "").strip().upper() or None,
        "crmRegion": (getattr(user, "crm_region", None) or "").strip().upper() or None,
        "crmMappingRegion": (getattr(user, "crm_mapping_region", None) or "").strip() or None,
        "crmDesignation": (getattr(user, "crm_designation", None) or "").strip() or None,
        "crmPhone": (getattr(user, "crm_phone", None) or "").strip() or None,
        "crmStates": (getattr(user, "crm_states", None) or "").strip() or None,
        "crmCities": (getattr(user, "crm_cities", None) or "").strip() or None,
    }


def list_crm_users_for_api(
    state: str | None = None,
    city: str | None = None,
    *,
    for_assign: bool = False,
    request=None,
    pipeline: str | None = None,
) -> list[dict]:
    """
    List CRM users for filters / assignment.
    When state or city is provided, only return users covering that territory.
    With no geo filter, scope to the viewer's region (national viewers see all).
    ``for_assign=True`` limits to RM / Manager / Dy Manager / Assistant Manager.
    ``pipeline=franchise`` applies TKPL franchise zonal team sheets; ``admission`` for admission sheet.
    """
    pipe = normalize_crm_pipeline(pipeline)
    state_s = (state or "").strip()
    city_s = (city or "").strip()
    viewer = _viewer_from_request(request)
    if for_assign and pipe == "franchise" and zonal_franchise_uses_full_handler_list(viewer):
        return [_user_api_dict(user) for user in all_assignable_handler_users()]
    if for_assign and pipe == "admission" and zonal_admission_uses_full_handler_list(viewer):
        return [_user_api_dict(user) for user in all_assignable_handler_users()]
    if state_s or city_s:
        users = crm_users_matching_geo_filter(state_s or None, city_s or None)
    elif request is not None:
        users = crm_users_matching_request_scope(request, pipe)
    else:
        users = list(crm_users_queryset())
    if for_assign:
        users = _filter_assignable_handlers(users)
        if request is not None and pipe:
            team = _zonal_team_users_for_context(request, state_s or None, city_s or None, pipe)
            users = _merge_user_lists(users, _filter_assignable_handlers(team))
    return [_user_api_dict(user) for user in users]


def assignee_candidates_for_lead(
    *,
    state: str | None = None,
    city: str | None = None,
    national: bool = False,
    assigner=None,
    franchise_lead: bool = False,
    admission_lead: bool = False,
) -> list[User]:
    """
    Users a lead may be assigned to — RM / Manager / Dy Manager / Assistant Manager only.
    Prefer territory match; national assigners fall back to full handler list.
    """
    if franchise_lead and zonal_franchise_uses_full_handler_list(assigner):
        return all_assignable_handler_users()
    if admission_lead and zonal_admission_uses_full_handler_list(assigner):
        return all_assignable_handler_users()
    if (state or "").strip() or (city or "").strip():
        matched = _filter_assignable_handlers(
            crm_users_matching_geo_filter(state, city)
        )
        if matched:
            return matched
    if national:
        return _filter_assignable_handlers(list(crm_users_queryset()))
    return []


def is_valid_assignee_for_lead(
    assignee: User,
    *,
    state: str | None = None,
    city: str | None = None,
    assigner=None,
    franchise_lead: bool = False,
    admission_lead: bool = False,
) -> bool:
    """Validate target is an assignable handler (RM/Manager/Dy/AM) in territory."""
    if not is_assignable_handler_user(assignee):
        return False
    if franchise_lead and zonal_franchise_uses_full_handler_list(assigner):
        return True
    if admission_lead and zonal_admission_uses_full_handler_list(assigner):
        return True
    assigner_email = str(getattr(assigner, "email", "") or "").strip().lower()
    national = assigner_email in CRM_SUPER_ADMIN_ASSIGN_EMAILS
    candidates = assignee_candidates_for_lead(
        state=state,
        city=city,
        national=national,
        assigner=assigner,
        franchise_lead=franchise_lead,
        admission_lead=admission_lead,
    )
    if not candidates and national:
        return True
    return any(u.id == assignee.id for u in candidates)


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
    # Do not expose an automatic/suggested manager. Assignment is an explicit
    # Zonal Manager action in the CRM.
    if include_suggestion:
        payload["suggestedAssignedUserId"] = None
        payload["suggestedAssignedUserLabel"] = None
    return payload
