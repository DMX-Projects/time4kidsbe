"""CRM admin API helpers — response shape matches timekids_crm_clone."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from .models import CrmLead, CrmLeadNote, CrmLeadSource, CrmLeadStatus, Enquiry, EnquiryType, KidsEnquiry, FranchiseEnquiry
from .crm_users import assigned_user_payload
from .meta_leads import format_meta_choice_label

CRM_SOURCE_FROM_API = {
    "website": CrmLeadSource.WEB,
    "facebook": CrmLeadSource.FB,
    "instagram": CrmLeadSource.INSTA,
    "web": CrmLeadSource.WEB,
    "fb": CrmLeadSource.FB,
    "insta": CrmLeadSource.INSTA,
    "july_lp": CrmLeadSource.JULY_LP,
    "july-lp": CrmLeadSource.JULY_LP,
    "july_meta": CrmLeadSource.JULY_META,
    "july-meta": CrmLeadSource.JULY_META,
    "lp_wb": CrmLeadSource.LP_WB,
    "lp-wb": CrmLeadSource.LP_WB,
    "google": "google",
    "admission": "admission",
    "contact": "contact",
    "landing": "landing",
    "campaign": "campaign",
}

CRM_SOURCE_TO_API = {
    CrmLeadSource.WEB: "website",
    CrmLeadSource.FB: "facebook",
    CrmLeadSource.INSTA: "instagram",
    CrmLeadSource.JULY_LP: "july_lp",
    CrmLeadSource.JULY_META: "july_meta",
    CrmLeadSource.LP_WB: "lp_wb",
}

FRANCHISE_CAMPAIGN_SOURCES = (
    CrmLeadSource.JULY_LP,
    CrmLeadSource.JULY_META,
    CrmLeadSource.LP_WB,
)

# Dedicated CRM logins restricted to Paid Campaign (franchise campaign channels only).
CAMPAIGN_ONLY_CRM_EMAILS = {
    "sachin.dhakate@time4education.com",
}

# Third-party viewers: paid campaign only, view-only, mobile/email hidden.
# Add new emails here — do NOT put Sachin here.
CAMPAIGN_EXTERNAL_VIEWER_EMAILS = {
    "campaign.viewer@gmail.com",
}

# Agency viewers: state-scoped, view-only, PII hidden.
# Bcwebwise = BCWW 6 Instant-Form states (landing + Facebook/Meta).
# Ants = West Bengal city landing pages only.
BCWEBWISE_AGENCY_EMAILS = {
    "bcwebwise.agency@gmail.com",
}
ANTS_AGENCY_EMAILS = {
    "ants.agency@gmail.com",
}
AGENCY_VIEWER_EMAILS = BCWEBWISE_AGENCY_EMAILS | ANTS_AGENCY_EMAILS

# Full state names stored on User.crm_states for zone scoping.
AGENCY_VIEWER_STATES: dict[str, tuple[str, ...]] = {
    "bcwebwise.agency@gmail.com": (
        "Tamil Nadu",
        "Karnataka",
        "Andhra Pradesh",
        "Kerala",
        "Telangana",
        "Maharashtra",
    ),
    "ants.agency@gmail.com": ("West Bengal",),
}

AGENCY_VIEWER_LABELS: dict[str, str] = {
    "bcwebwise.agency@gmail.com": "Bcwebwise Agency",
    "ants.agency@gmail.com": "Ants Agency",
}


def _viewer_email(request=None, user=None) -> str:
    viewer = user
    if viewer is None and request is not None:
        viewer = getattr(request, "user", None)
    return str(getattr(viewer, "email", "") or "").strip().lower()


def is_agency_crm_user(request=None, user=None) -> bool:
    email = _viewer_email(request=request, user=user)
    return bool(email and email in AGENCY_VIEWER_EMAILS)


def is_bcwebwise_agency_user(request=None, user=None) -> bool:
    email = _viewer_email(request=request, user=user)
    return bool(email and email in BCWEBWISE_AGENCY_EMAILS)


def is_ants_agency_user(request=None, user=None) -> bool:
    email = _viewer_email(request=request, user=user)
    return bool(email and email in ANTS_AGENCY_EMAILS)


def is_campaign_only_crm_user(request=None, user=None) -> bool:
    """Paid-campaign-only logins (Sachin + generic campaign.viewer). Not agency viewers."""
    email = _viewer_email(request=request, user=user)
    return bool(
        email
        and (
            email in CAMPAIGN_ONLY_CRM_EMAILS
            or email in CAMPAIGN_EXTERNAL_VIEWER_EMAILS
        )
    )


def is_campaign_external_viewer(request=None, user=None) -> bool:
    """Third-party: no mobile/email, cannot edit (campaign.viewer + agency logins)."""
    email = _viewer_email(request=request, user=user)
    return bool(
        email
        and (email in CAMPAIGN_EXTERNAL_VIEWER_EMAILS or email in AGENCY_VIEWER_EMAILS)
    )


def is_restricted_crm_viewer(request=None, user=None) -> bool:
    """Any locked third-party / campaign-only CRM login (readonly + limited sources)."""
    return is_campaign_only_crm_user(request=request, user=user) or is_agency_crm_user(
        request=request, user=user
    )


def redact_lead_for_campaign_viewer(data: dict | None) -> dict | None:
    """Hide PII and mark lead non-editable for third-party campaign viewers."""
    if not data:
        return data
    out = dict(data)
    out["mobile"] = ""
    out["email"] = ""
    out["editable"] = False
    out["canAssignUsers"] = False
    out["campaignViewer"] = True
    return out

GOOGLE_CAMPAIGN_SOURCES = (
    CrmLeadSource.JULY_LP,
    CrmLeadSource.LP_WB,
)

# Inline LP form page names (separate from dynamic UTM campaign).
LP_FORM_NAME = {
    CrmLeadSource.JULY_LP: "lp-tkktam",
    CrmLeadSource.JULY_META: "meta-tkktam",
    CrmLeadSource.LP_WB: "lp-wb",
}

_GOOGLE_ADS_URL_MARKERS = (
    "gclid=",
    "gad_source=",
    "gad_campaignid=",
    "gbraid=",
    "wbraid=",
)


def is_google_ads_landing_url(url: str | None) -> bool:
    """True when the stored landing URL carries Google Ads auto-tagging params."""
    text = (url or "").lower()
    return any(marker in text for marker in _GOOGLE_ADS_URL_MARKERS)


def effective_crm_source(lead: CrmLead) -> str:
    """
    Channel source for CRM.
    Google Ads traffic on any LP (including Meta-named LP) counts as Google.
    """
    if is_google_ads_landing_url(getattr(lead, "landing_page_url", None)):
        return CrmLeadSource.JULY_LP
    return lead.source or ""


def crm_lead_form_name(lead: CrmLead) -> str:
    """Which LP form was used (lp-tkktam / meta-tkktam / lp-wb). Blank for Instant Forms."""
    utm_source = (getattr(lead, "utm_source", None) or "").strip().lower()
    if utm_source == "facebook_lead_ads":
        return ""

    raw = getattr(lead, "raw_payload", None) or {}
    if isinstance(raw, dict):
        page = str(raw.get("pageType") or raw.get("page_type") or "").strip().lower()
        if page in ("meta-tkktam", "lp-tkktam", "lp-wb"):
            return page

    url = (getattr(lead, "landing_page_url", None) or "").lower()
    if "timekids-meta-tkktam" in url:
        return "meta-tkktam"
    if "timekids-lp-wb" in url:
        return "lp-wb"
    if "timekids-lp-tkktam" in url:
        return "lp-tkktam"

    return LP_FORM_NAME.get(lead.source, "")


def campaign_channel_api_key(source: str | None, landing_page_url: str | None = None) -> str:
    """Map stored form source to CRM channel key (BCWW Google vs Ants WB vs META)."""
    if is_google_ads_landing_url(landing_page_url):
        return "google"
    api = source_to_api(source) if source else ""
    if api == "july_lp":
        return "google"
    if api == "lp_wb":
        return "lp_wb"  # Ants — West Bengal Google LP
    return api or ""


def normalize_source_from_api(value: str | None) -> str:
    raw = (value or "").strip().lower()
    mapped = CRM_SOURCE_FROM_API.get(raw)
    if mapped:
        return mapped
    return raw


def source_to_api(value: str | None) -> str:
    if not value:
        return "website"
    return CRM_SOURCE_TO_API.get(value, value)


def _dt(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def note_to_dict(note: CrmLeadNote) -> dict:
    return {
        "id": str(note.id),
        "content": note.content,
        "createdAt": _dt(note.created_at),
    }

def unified_note_to_dict(note) -> dict:
    return {
        "id": str(note.id),
        "content": note.content,
        "createdAt": _dt(note.created_at),
        "status": getattr(note, "status", "") or "",
    }

def _get_unified_notes(lead_kind: str, numeric_id: int) -> list:
    from .models import UnifiedLeadNote
    lead_id = f"{lead_kind}_{numeric_id}"
    notes = UnifiedLeadNote.objects.filter(lead_id=lead_id)
    return [unified_note_to_dict(n) for n in notes]


def _split_notes_and_notification_logs(notes: list[dict]) -> tuple[list[dict], list[dict]]:
    """Pull Email/WhatsApp nurture entries into notificationLogs for History."""
    regular: list[dict] = []
    notifications: list[dict] = []
    for note in notes:
        content = str(note.get("content") or "")
        if content.startswith("[Email]"):
            notifications.append(
                {
                    "id": note.get("id"),
                    "type": "email",
                    "status": "sent",
                    "createdAt": note.get("createdAt"),
                    "content": content,
                }
            )
        elif content.startswith("[WhatsApp]"):
            notifications.append(
                {
                    "id": note.get("id"),
                    "type": "whatsapp",
                    "status": "sent",
                    "createdAt": note.get("createdAt"),
                    "content": content,
                }
            )
        else:
            regular.append(note)
    return regular, notifications


def _attach_history_fields(data: dict, lead_kind: str, numeric_id: int, *, extra_notes: list | None = None) -> dict:
    notes = list(extra_notes or []) + _get_unified_notes(lead_kind, numeric_id)
    regular, notifications = _split_notes_and_notification_logs(notes)
    data["notes"] = regular
    data["auditLogs"] = data.get("auditLogs") or []
    data["notificationLogs"] = notifications
    data["callHistory"] = data.get("callHistory") or []
    return data


def log_crm_communication(
    raw_lead_id: str,
    channel: str,
    *,
    subject: str = "",
    body: str = "",
    to_value: str = "",
    actor=None,
) -> dict | None:
    """
    Persist an Email/WhatsApp nurture action into History (UnifiedLeadNote).
    Returns the created note dict, or None if lead id is invalid.
    """
    from .models import UnifiedLeadNote

    kind, numeric_id = parse_lead_id(raw_lead_id)
    channel_key = (channel or "").strip().lower()
    if channel_key not in ("email", "whatsapp"):
        return None

    content = "[Email] Email sent" if channel_key == "email" else "[WhatsApp] WhatsApp sent"

    note = UnifiedLeadNote.objects.create(
        lead_id=f"{kind}_{numeric_id}",
        content=content,
        status="",
    )
    return unified_note_to_dict(note)


def lead_to_dict(lead: CrmLead, *, include_detail: bool = False) -> dict:
    # LP / Meta / LP-WB forms only collect state + city — never invent a centre.
    is_franchise_campaign = lead.source in FRANCHISE_CAMPAIGN_SOURCES

    if is_franchise_campaign:
        city = lead.city or ""
        state = lead.state or ""
        centre_name = ""
    else:
        franchise = _resolved_franchise_for_crm_lead(lead)
        centre_name, centre_phone, centre_email = _franchise_centre_contact(franchise)
        from franchises.franchise_geo import effective_city

        city = effective_city(franchise) if franchise else (lead.city or "")
        state = _franchise_state(franchise) if franchise else (lead.state or "")
        if not centre_name:
            centre_name = (lead.preferred_centre_location or "").strip()

    data = {
        "id": f"crm-{lead.id}",
        "leadKind": "crm",
        "editable": True,
        "fullName": lead.full_name,
        "mobile": lead.mobile,
        "email": lead.email or "",
        "city": city,
        "state": state,
        "preferredCentreLocation": centre_name,
        "franchiseType": lead.franchise_type or None,
        "investmentRange": lead.investment_range or None,
        "expectedStartDate": (
            format_meta_choice_label(lead.expected_start_date)
            if (lead.expected_start_date or "").strip()
            else None
        ),
        "source": source_to_api(effective_crm_source(lead)),
        "landingPageUrl": lead.landing_page_url or "",
        "formName": crm_lead_form_name(lead),
        "pageType": crm_lead_form_name(lead) or (lead.utm_source or source_to_api(effective_crm_source(lead)) or ""),
        # Dynamic UTM params from the ad URL (Source / Medium / Campaign / Content / Term)
        "campaign": lead.utm_campaign or "",
        "utmSource": lead.utm_source or "",
        "utmMedium": lead.utm_medium or "",
        "utmCampaign": lead.utm_campaign or "",
        "utmContent": getattr(lead, "utm_content", "") or "",
        "utmTerm": getattr(lead, "utm_term", "") or "",
        "comments": lead.comments or "",
        "status": lead.status,
        "meetingDate": _dt(lead.meeting_date),
        "nextFollowUpDate": _dt(lead.next_follow_up_date),
        "createdAt": _dt(lead.created_at),
        "updatedAt": _dt(lead.updated_at),
        **assigned_user_payload(
            getattr(lead, "assigned_user", None),
            state=state,
            city=city,
            include_suggestion=include_detail,
        ),
    }
    if include_detail:
        legacy_notes = [note_to_dict(n) for n in lead.notes.all()]
        _attach_history_fields(data, "crm", lead.id, extra_notes=legacy_notes)
    return data


def _query_params(request):
    reminder_params = getattr(request, "_reminders_query_params", None)
    if reminder_params is not None:
        return reminder_params
    return getattr(request, "query_params", None) or request.GET


def _parse_request_dates(request):
    params = _query_params(request)
    raw_start = (params.get("startDate") or "").strip()
    raw_end = (params.get("endDate") or "").strip()
    start = parse_datetime(raw_start) or (parse_date(raw_start) if raw_start else None)
    end = parse_datetime(raw_end) or (parse_date(raw_end) if raw_end else None)
    return start, end


def _request_centre_ids(request) -> list[int]:
    if is_campaign_only_crm_user(request=request):
        return []
    raw = (_query_params(request).get("centreId") or _query_params(request).get("centre_id") or "").strip()
    if not raw:
        return []
    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            continue
    return ids


def _request_centre_filter(request) -> int | None:
    """Single centre id when exactly one is selected; otherwise None (use ``_request_centre_ids``)."""
    ids = _request_centre_ids(request)
    return ids[0] if len(ids) == 1 else None


def _franchises_for_centre_filter(request):
    ids = _request_centre_ids(request)
    if not ids:
        return []
    from franchises.models import Franchise

    return list(Franchise.objects.filter(pk__in=ids, is_active=True))


def _franchise_for_centre_filter(request):
    centres = _franchises_for_centre_filter(request)
    return centres[0] if len(centres) == 1 else None


def _filter_enquiry_qs_by_centre(qs, request):
    ids = _request_centre_ids(request)
    if not ids:
        return qs
    return qs.filter(franchise_id__in=ids)


def _filter_landing_qs_by_centre(qs, request):
    franchises = _franchises_for_centre_filter(request)
    if not franchises:
        return qs
    from django.db.models import Q

    q = Q()
    for franchise in franchises:
        name = (franchise.name or "").strip()
        if not name:
            continue
        q |= Q(location__iexact=name) | Q(centre_name__iexact=name)
    if not q:
        return qs.none()
    return qs.filter(q)


def _filter_crm_qs_by_centre(qs, request):
    franchises = _franchises_for_centre_filter(request)
    if not franchises:
        return qs
    from django.db.models import Q

    q = Q()
    for franchise in franchises:
        name = (franchise.name or "").strip()
        if name:
            q |= Q(preferred_centre_location__iexact=name)
    if not q:
        return qs.none()
    return qs.filter(q)


def _request_city_filter(request) -> str | None:
    city = (_query_params(request).get("city") or "").strip()
    return city or None


def _franchise_state(franchise) -> str:
    if not franchise:
        return ""
    from franchises.franchise_geo import state_to_display

    raw = (getattr(franchise, "statename", None) or getattr(franchise, "state", None) or "").strip()
    return state_to_display(raw) if raw else ""


def _franchise_centre_contact(franchise) -> tuple[str, str, str]:
    if not franchise:
        return "", "", ""
    name = (getattr(franchise, "name", None) or "").strip()
    phone = (getattr(franchise, "contact_phone", None) or getattr(franchise, "phoneno", None) or "").strip()
    email = (getattr(franchise, "contact_email", None) or getattr(franchise, "email", None) or "").strip()
    return name, phone, email


def _resolved_franchise_for_landing(row: KidsEnquiry):
    from enquiries.landing_submit import _lookup_franchise

    city = (row.city or "").strip()
    location = (row.location or row.centre_name or "").strip()
    return _lookup_franchise(city, location)


def _resolved_franchise_for_crm_lead(lead: CrmLead):
    from enquiries.landing_submit import _lookup_franchise

    city = (lead.city or "").strip()
    location = (lead.preferred_centre_location or "").strip()
    if not location:
        return None
    return _lookup_franchise(city, location)


def _centre_names_in_city(city: str) -> list[str]:
    from franchises.franchise_geo import filter_queryset_by_city
    from franchises.models import Franchise

    return list(
        filter_queryset_by_city(Franchise.objects.filter(is_active=True), city)
        .values_list("name", flat=True)
        .distinct()
    )


def _filter_qs_by_city(
    qs,
    request,
    *,
    field_name: str = "city",
    franchise_city_fields: tuple[str, ...] = (),
):
    city = _request_city_filter(request)
    if not city:
        return qs
    from franchises.franchise_geo import city_query_variants

    city_q = Q()
    for c in [x.strip() for x in city.split(",") if x.strip()]:
        for variant in city_query_variants(c):
            city_q |= Q(**{f"{field_name}__iexact": variant})
            for franchise_field in franchise_city_fields:
                city_q |= Q(**{f"{franchise_field}__iexact": variant})
    return qs.filter(city_q)


def _filter_landing_qs_by_city(qs, request):
    city = _request_city_filter(request)
    if not city:
        return qs
    from franchises.franchise_geo import city_query_variants

    city_q = Q()
    for c in [x.strip() for x in city.split(",") if x.strip()]:
        for variant in city_query_variants(c):
            city_q |= Q(city__iexact=variant)
        centre_names = _centre_names_in_city(c)
        if centre_names:
            city_q |= Q(location__in=centre_names) | Q(centre_name__in=centre_names)
    return qs.filter(city_q)


def _filter_crm_qs_by_city(qs, request):
    city = _request_city_filter(request)
    if not city:
        return qs
    from franchises.franchise_geo import city_query_variants

    city_q = Q()
    for c in [x.strip() for x in city.split(",") if x.strip()]:
        for variant in city_query_variants(c):
            city_q |= Q(city__iexact=variant)
        centre_names = _centre_names_in_city(c)
        if centre_names:
            city_q |= Q(preferred_centre_location__in=centre_names)
    return qs.filter(city_q)


def unified_crm_cities(state: str | None = None, request=None) -> list[str]:
    """City names for CRM filter dropdown (franchise locations), optionally filtered by state."""
    from franchises.models import Franchise
    from enquiries.models import FranchiseEnquiry
    from django.db.models import Q
    from accounts.crm_zones import (
        clamp_requested_states,
        city_match_variants,
        filter_franchise_qs_by_zone,
        resolve_scope_cities,
        resolve_scope_state_codes,
        scope_city_names,
        scope_match_values,
        state_in_codes,
    )
    from franchises.franchise_geo import state_to_display

    scope_user_id = None
    if request is not None:
        params = getattr(request, "query_params", None) or getattr(request, "GET", {})
        raw_scope = (params.get("userId") or params.get("scopeUserId") or "").strip() or None
        if raw_scope:
            from enquiries.crm_users import sanitize_crm_scope_user_id

            scope_user_id = sanitize_crm_scope_user_id(raw_scope)

    codes = resolve_scope_state_codes(request, scope_user_id) if request is not None else None
    # Scoped CRM (zone or region, optionally narrowed by filter user): full city master list.
    if codes is not None:
        state_scoped = state
        if request is not None and state:
            # Clamp requested states to the effective scope (viewer ∩ filter user).
            allowed_cf = {a.casefold() for a in scope_match_values(codes)}
            kept: list[str] = []
            for part in state.split(","):
                s = part.strip()
                if not s:
                    continue
                if s.casefold() in allowed_cf or state_in_codes(s, codes):
                    kept.append(state_to_display(s) or s)
            state_scoped = ",".join(kept) if kept else None
        cities = scope_city_names(codes, state_scoped)
        user_cities = resolve_scope_cities(request, scope_user_id) if request is not None else None
        if user_cities is not None:
            allowed = {c.casefold() for c in user_cities}
            expanded = {v.casefold() for c in user_cities for v in city_match_variants(c)}
            cities = [c for c in cities if c.casefold() in expanded or c.casefold() in allowed]
            # Always include configured city names even if not yet in franchise master.
            have = {c.casefold() for c in cities}
            for c in user_cities:
                if c.casefold() not in have:
                    cities.append(c)
                    have.add(c.casefold())
            cities = sorted(cities, key=str.casefold)
        return cities

    cities: set[str] = set()
    state = clamp_requested_states(request, state) if request is not None else state

    if state:
        state_list = [x.strip() for x in state.split(",") if x.strip()]
        
        # Filter Franchises by state
        franchise_q = Q()
        for s in state_list:
            franchise_q |= Q(state__iexact=s) | Q(statename__iexact=s)
        franchise_qs = Franchise.objects.filter(franchise_q, is_active=True)
        if request is not None:
            franchise_qs = filter_franchise_qs_by_zone(franchise_qs, request)
        for f in franchise_qs:
            name = (f.cityname or f.city or "").strip().title()
            if name:
                cities.add(name)

        # Filter FranchiseEnquiries by state
        fe_q = Q()
        for s in state_list:
            fe_q |= Q(state__iexact=s)
        for c in FranchiseEnquiry.objects.filter(fe_q).exclude(city__isnull=True).exclude(city="").values_list("city", flat=True).distinct():
            cities.add(c.strip().title())
    else:
        from franchises.franchise_geo import cities_from_franchises
        for loc in cities_from_franchises():
            name = (loc.get("city_name") or loc.get("city") or "").strip().title()
            if name:
                cities.add(name)
        for c in FranchiseEnquiry.objects.exclude(city__isnull=True).exclude(city="").values_list("city", flat=True).distinct():
            cities.add(c.strip().title())

    return sorted(list(cities), key=str.casefold)


def _request_source_filter(request) -> str | None:
    if is_agency_crm_user(request=request):
        # Landing pages + Facebook/Meta (and WB LP for Ants) — never Admission/Franchise website.
        return "agency"
    if is_campaign_only_crm_user(request=request):
        # Hard-lock this account to Paid Campaign view.
        return "campaign"
    return (_query_params(request).get("source") or "").strip().lower() or None


def _request_user_filter(request) -> str | None:
    """``userId`` query: assignable handler id, ``unassigned``, or empty (all)."""
    if is_restricted_crm_viewer(request=request):
        return None
    from enquiries.crm_users import sanitize_crm_filter_user_id

    return sanitize_crm_filter_user_id(_query_params(request).get("userId"))


def _apply_assigned_user_filter(qs, request):
    """Apply the authorized manager assignment dropdown filter."""
    user_filter = _request_user_filter(request)
    if not user_filter:
        return qs
    if user_filter in ("unassigned", "none", "null"):
        return qs.filter(assigned_user__isnull=True)
    return qs.filter(assigned_user_id=int(user_filter))


def _apply_viewer_assignment_scope(qs, request):
    """Handlers see assigned leads; Regional/Zonal/Super Admins keep broader scope."""
    from .crm_users import filter_leads_for_crm_viewer

    return filter_leads_for_crm_viewer(qs, request)


def _is_franchise_assignable_object(obj) -> bool:
    """True when lead belongs to the franchise CRM pipeline (not admission)."""
    model = type(obj).__name__.lower()
    if model in ("crmlead", "franchiseenquiry"):
        return True
    if model == "enquiry":
        return (getattr(obj, "enquiry_type", None) or "").strip().upper() == "FRANCHISE"
    return False


def _is_admission_assignable_object(obj) -> bool:
    """True when lead belongs to the admission CRM pipeline."""
    model = type(obj).__name__.lower()
    if model == "kidsenquiry":
        return True
    if model == "enquiry":
        et = (getattr(obj, "enquiry_type", None) or "").strip().upper()
        return et in ("ADMISSION", "CONTACT")
    return False


def _maybe_assign_lead(obj, request, data: dict | None = None) -> bool:
    """
    Apply an explicit Regional/Zonal/Super Admin assignment to a permitted handler.
    Leads remain unassigned when ``assignedUserId`` is not supplied.
    """
    data = data or {}
    if "assignedUserId" not in data:
        return False

    raw = data.get("assignedUserId")
    if raw in (None, "", "unassigned", "null"):
        return False
    request_user = getattr(request, "user", None) if request is not None else None
    state = (getattr(obj, "state", None) or "").strip()
    city = (getattr(obj, "city", None) or "").strip()
    from .crm_users import is_meta_instant_form_lead, is_valid_assignee_for_lead, user_can_assign_crm_leads

    if not user_can_assign_crm_leads(request_user):
        return False
    try:
        from accounts.models import User, UserRole

        uid = int(raw)
    except (TypeError, ValueError):
        return False
    user = User.objects.filter(pk=uid, role__iexact=UserRole.CRM.value, is_active=True).first()
    if not user:
        return False
    # Meta Instant Forms: validate assignee against state only (city is free-text).
    ignore_city = is_meta_instant_form_lead(obj)
    if not is_valid_assignee_for_lead(
        user,
        state=state,
        city=city,
        assigner=request_user,
        franchise_lead=_is_franchise_assignable_object(obj),
        admission_lead=_is_admission_assignable_object(obj),
        ignore_city=ignore_city,
    ):
        raise ValueError("Selected user is not in this lead's territory.")
    changed = getattr(obj, "assigned_user_id", None) != user.pk
    obj.assigned_user = user
    return changed


def _notify_explicit_assignment(obj, request) -> None:
    """Best-effort assignee email; assignment remains saved if email delivery fails."""
    import logging

    from .emails import send_crm_lead_assignment_email

    try:
        send_crm_lead_assignment_email(
            obj,
            assigned_by=getattr(request, "user", None) if request is not None else None,
        )
    except Exception:
        logging.getLogger(__name__).exception(
            "Failed to send CRM assignment email for %s id=%s",
            type(obj).__name__,
            getattr(obj, "pk", None),
        )


def _include_crm(source_filter: str | None) -> bool:
    if not source_filter:
        return True
    if source_filter == "agency":
        # Ants: landing only. Bcwebwise: Facebook/Meta + landing (crm included).
        # Caller still scopes by request; Ants is excluded inside _filter_crm_qs.
        return True
    if source_filter in ("campaign", "franchise_all"):
        return True
    return source_filter in {
        "google",
        "july_lp", "july-lp", "july_meta", "july-meta", "lp_wb", "lp-wb",
    }


def _include_franchise_enquiry(source_filter: str | None) -> bool:
    if not source_filter:
        return True
    if source_filter == "agency":
        return False
    return source_filter in {"franchise", "franchise_all"}


def _include_admission(source_filter: str | None) -> bool:
    """Website admission form (EnquiryType.ADMISSION)."""
    if not source_filter:
        return True
    if source_filter == "agency":
        return False
    return source_filter in {"admission", "admission_all"}


def _include_contact(source_filter: str | None) -> bool:
    """Centerpage contact enquiries."""
    if not source_filter:
        return True
    if source_filter == "agency":
        return False
    return source_filter in {"contact", "admission_all"}


def _include_landing(source_filter: str | None) -> bool:
    """City landing-page leads (``kids_enquiry``)."""
    if not source_filter:
        return True
    return source_filter in {"landing", "admission_all", "agency"}


def _enquiry_status_to_crm(status: str) -> str:
    if status == "pending":
        return "new"
    if status == "in-progress":
        return "contacted"
    if status == "closed":
        return "converted"
    return status


def _crm_status_matches_enquiry(crm_status: str, enquiry_status: str) -> bool:
    mapped = _enquiry_status_to_crm(enquiry_status)
    return mapped == crm_status


def _crm_status_to_enquiry(crm_status: str) -> str:
    return crm_status


def _landing_crm_status(row: KidsEnquiry) -> str:
    payload = row.raw_payload if isinstance(row.raw_payload, dict) else {}
    value = str(payload.get("crm_status") or "").strip()
    return value or "untouched"


def _valid_crm_statuses() -> set[str]:
    return {choice.value for choice in CrmLeadStatus}


def enquiry_to_dict(enquiry: Enquiry, *, include_detail: bool = False) -> dict:
    franchise = enquiry.franchise if enquiry.franchise_id else None
    centre_name, centre_phone, centre_email = _franchise_centre_contact(franchise)
    from franchises.franchise_geo import effective_city

    city = effective_city(franchise) if franchise else (enquiry.city or "")
    state = _franchise_state(franchise) if franchise else ""
    source = "admission" if enquiry.enquiry_type == EnquiryType.ADMISSION else "contact"
    from enquiries.models import UnifiedLeadNote
    latest_note = UnifiedLeadNote.objects.filter(lead_id=f"enquiry_{enquiry.id}").order_by("-created_at").first()
    updated_at = latest_note.created_at if latest_note else enquiry.created_at

    data = {
        "id": f"enquiry-{enquiry.id}",
        "leadKind": "enquiry",
        "editable": True,
        "fullName": enquiry.name,
        "mobile": enquiry.phone or "",
        "email": enquiry.email or "",
        "city": city,
        "state": state,
        "preferredCentreLocation": centre_name,
        "centreName": centre_name,
        "franchiseType": None,
        "investmentRange": None,
        "expectedStartDate": None,
        "source": source,
        "enquiryType": enquiry.enquiry_type,
        "childAge": enquiry.child_age or "",
        "comments": enquiry.message or "",
        "status": _enquiry_status_to_crm(enquiry.status),
        "meetingDate": _dt(enquiry.meeting_date),
        "nextFollowUpDate": _dt(enquiry.next_follow_up_date),
        "createdAt": _dt(enquiry.created_at),
        "updatedAt": _dt(updated_at),
        **assigned_user_payload(
            getattr(enquiry, "assigned_user", None),
            state=state,
            city=city,
            include_suggestion=include_detail,
        ),
    }
    if include_detail:
        _attach_history_fields(data, "enquiry", enquiry.id)
    return data


def franchise_enquiry_to_dict(enquiry: FranchiseEnquiry, *, include_detail: bool = False) -> dict:
    franchise = enquiry.franchise if enquiry.franchise_id else None
    centre_name, centre_phone, centre_email = _franchise_centre_contact(franchise)
    from franchises.franchise_geo import effective_city

    city = effective_city(franchise) if franchise else (enquiry.city or "")
    state = _franchise_state(franchise) if franchise else (enquiry.state or "")
    from enquiries.models import UnifiedLeadNote
    latest_note = UnifiedLeadNote.objects.filter(lead_id=f"franchiseenquiry_{enquiry.id}").order_by("-created_at").first()
    updated_at = latest_note.created_at if latest_note else enquiry.created_at

    data = {
        "id": f"franchiseenquiry-{enquiry.id}",
        "leadKind": "franchiseenquiry",
        "editable": True,
        "fullName": enquiry.name,
        "mobile": enquiry.phone or "",
        "email": enquiry.email or "",
        "city": city,
        "state": state,
        "preferredCentreLocation": centre_name,
        "franchiseType": None,
        "investmentRange": None,
        "expectedStartDate": None,
        "source": "franchise",
        "enquiryType": "FRANCHISE",
        "comments": enquiry.message or "",
        "status": enquiry.status,
        "meetingDate": _dt(enquiry.meeting_date),
        "nextFollowUpDate": _dt(enquiry.next_follow_up_date),
        "createdAt": _dt(enquiry.created_at),
        "updatedAt": _dt(updated_at),
        **assigned_user_payload(
            getattr(enquiry, "assigned_user", None),
            state=state,
            city=city,
            include_suggestion=include_detail,
        ),
    }
    if include_detail:
        _attach_history_fields(data, "franchiseenquiry", enquiry.id)
    return data


def landing_to_dict(row: KidsEnquiry, *, include_detail: bool = False) -> dict:
    mobile = (row.mobileno or row.mobile or "").strip()
    franchise = _resolved_franchise_for_landing(row)
    centre_name, centre_phone, centre_email = _franchise_centre_contact(franchise)
    from franchises.franchise_geo import effective_city

    city = effective_city(franchise) if franchise else (row.city or "").strip()
    state = _franchise_state(franchise) if franchise else (row.state or "").strip()
    if not centre_name:
        centre_name = (row.centre_name or row.location or "").strip()
    if not centre_phone:
        centre_phone = (row.centre_phone or "").strip()
    if not centre_email:
        centre_email = (row.centre_email or "").strip()
    data = {
        "id": f"landing-{row.id}",
        "leadKind": "landing",
        "editable": True,
        "fullName": row.name or "",
        "mobile": mobile,
        "email": (row.email or "").strip(),
        "city": city,
        "state": state,
        "preferredCentreLocation": centre_name,
        "franchiseType": None,
        "investmentRange": None,
        "expectedStartDate": None,
        "source": "landing",
        "landingSource": (row.source or "").strip(),
        "enquiryType": (row.enquiry_type or "").strip(),
        "comments": "",
        "status": _landing_crm_status(row),
        "meetingDate": _dt(row.meeting_date),
        "nextFollowUpDate": _dt(row.next_follow_up_date),
        "createdAt": _dt(row.created_date),
        "updatedAt": _dt(row.created_date),
        **assigned_user_payload(
            getattr(row, "assigned_user", None),
            state=state,
            city=city,
            include_suggestion=include_detail,
        ),
    }
    if include_detail:
        _attach_history_fields(data, "landing", row.id)
        data["centrePhone"] = centre_phone
        data["centreEmail"] = centre_email
    return data


def parse_lead_id(raw_id: str) -> tuple[str, int]:
    value = str(raw_id or "").strip()
    if "-" in value:
        kind, pk = value.split("-", 1)
        return kind.lower(), int(pk)
    return "crm", int(value)


def _filter_crm_qs(
    request,
    *,
    apply_campaign_filter: bool = True,
    apply_medium_filter: bool = True,
):
    params = _query_params(request)
    qs = CrmLead.objects.all()
    # Unused /crm/web|fb|insta forms — never surface those leads in CRM admin.
    qs = qs.filter(source__in=FRANCHISE_CAMPAIGN_SOURCES)
    source_filter = _request_source_filter(request)
    if source_filter and _include_crm(source_filter):
        if source_filter == "agency":
            # Bcwebwise: Facebook Instant Forms + Meta LP only.
            # Ants: West Bengal city landing pages only (no campaign CrmLead rows).
            if is_ants_agency_user(request=request):
                return CrmLead.objects.none()
            if is_bcwebwise_agency_user(request=request):
                qs = qs.filter(source=CrmLeadSource.JULY_META)
        elif source_filter not in ("campaign", "franchise_all"):
            google_ads_landing_q = (
                Q(landing_page_url__icontains="gclid=")
                | Q(landing_page_url__icontains="gad_source=")
                | Q(landing_page_url__icontains="gad_campaignid=")
                | Q(landing_page_url__icontains="gbraid=")
                | Q(landing_page_url__icontains="wbraid=")
            )
            if source_filter == "google":
                # Google LP/WB sources + any Meta LP submit that arrived via Google Ads.
                qs = qs.filter(Q(source__in=GOOGLE_CAMPAIGN_SOURCES) | google_ads_landing_q)
            else:
                mapped = normalize_source_from_api(source_filter)
                if mapped in FRANCHISE_CAMPAIGN_SOURCES:
                    qs = qs.filter(source=mapped)
                    # Meta Instant Form / Meta LP organic only — not Google Ads clicks on Meta LP.
                    if mapped == CrmLeadSource.JULY_META:
                        qs = qs.exclude(google_ads_landing_q)
    elif source_filter and not _include_crm(source_filter):
        return CrmLead.objects.none()

    if apply_campaign_filter:
        campaign_value = (params.get("campaign") or params.get("utmCampaign") or "").strip()
        if campaign_value:
            qs = qs.filter(utm_campaign__iexact=campaign_value)

    if apply_medium_filter:
        medium_value = (params.get("medium") or params.get("utmMedium") or "").strip()
        if medium_value:
            qs = qs.filter(utm_medium__iexact=medium_value)

    status_value = (params.get("status") or "").strip()
    if status_value:
        qs = qs.filter(status=status_value)

    search = (params.get("search") or "").strip()
    if search:
        qs = qs.filter(
            Q(full_name__icontains=search)
            | Q(mobile__icontains=search)
            | Q(email__icontains=search)
            | Q(city__icontains=search)
            | Q(state__icontains=search)
            | Q(preferred_centre_location__icontains=search)
            | Q(source__icontains=search)
        )

    start, end = _parse_request_dates(request)
    if start:
        qs = qs.filter(created_at__gte=start)
    if end:
        qs = qs.filter(created_at__lte=end)

    state_value = (params.get("state") or "").strip()
    if state_value:
        from accounts.crm_zones import clamp_requested_states

        state_value = clamp_requested_states(request, state_value) or ""
        state_queries = Q()
        for s in [x.strip() for x in state_value.split(",") if x.strip()]:
            state_queries |= Q(state__iexact=s)
        qs = qs.filter(state_queries)

    qs = _filter_crm_qs_by_city(qs, request)
    qs = _filter_crm_qs_by_centre(qs, request)
    qs = _apply_assigned_user_filter(qs, request)
    from accounts.crm_zones import filter_crm_lead_qs_by_zone

    qs = filter_crm_lead_qs_by_zone(qs, request)
    return _apply_viewer_assignment_scope(qs, request).order_by("-created_at")


def unified_crm_campaign_names(request) -> list[str]:
    """Distinct UTM / Meta form campaign names for Paid Campaign filter dropdown."""
    qs = _filter_crm_qs(request, apply_campaign_filter=False, apply_medium_filter=False)
    names = {
        (name or "").strip()
        for name in qs.exclude(utm_campaign="").values_list("utm_campaign", flat=True).distinct()
        if (name or "").strip()
    }
    return sorted(names, key=str.casefold)


def unified_crm_medium_names(request) -> list[str]:
    """Distinct UTM medium values for Paid Campaign filter dropdown."""
    qs = _filter_crm_qs(request, apply_campaign_filter=False, apply_medium_filter=False)
    names = {
        (name or "").strip()
        for name in qs.exclude(utm_medium="").values_list("utm_medium", flat=True).distinct()
        if (name or "").strip()
    }
    return sorted(names, key=str.casefold)


def _filter_enquiry_qs(request, enquiry_type: str):
    params = _query_params(request)
    source_filter = _request_source_filter(request)
    if enquiry_type == EnquiryType.ADMISSION and not _include_admission(source_filter):
        return Enquiry.objects.none()
    if enquiry_type == EnquiryType.CONTACT and not _include_contact(source_filter):
        return Enquiry.objects.none()

    qs = Enquiry.objects.filter(enquiry_type=enquiry_type).select_related("franchise")

    status_value = (params.get("status") or "").strip()
    if status_value:
        matching = [
            row["status"]
            for row in Enquiry.objects.filter(enquiry_type=enquiry_type).values("status").distinct()
            if _crm_status_matches_enquiry(status_value, row["status"])
        ]
        if matching:
            qs = qs.filter(status__in=matching)
        else:
            return Enquiry.objects.none()

    search = (params.get("search") or "").strip()
    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
            | Q(city__icontains=search)
            | Q(message__icontains=search)
            | Q(franchise__name__icontains=search)
            | Q(enquiry_type__icontains=search)
        )

    start, end = _parse_request_dates(request)
    if start:
        qs = qs.filter(created_at__gte=start)
    if end:
        qs = qs.filter(created_at__lte=end)

    state_value = (params.get("state") or "").strip()
    if state_value:
        from accounts.crm_zones import clamp_requested_states

        state_value = clamp_requested_states(request, state_value) or ""
        state_queries = Q()
        for s in [x.strip() for x in state_value.split(",") if x.strip()]:
            state_queries |= Q(franchise__state__iexact=s) | Q(franchise__statename__iexact=s) | Q(franchise__isnull=True)
        qs = qs.filter(state_queries)

    qs = _filter_qs_by_city(
        qs,
        request,
        field_name="city",
        franchise_city_fields=("franchise__city", "franchise__cityname"),
    )
    qs = _filter_enquiry_qs_by_centre(qs, request)
    qs = _apply_assigned_user_filter(qs, request)
    from accounts.crm_zones import filter_enquiry_qs_by_zone

    qs = filter_enquiry_qs_by_zone(qs, request)
    return _apply_viewer_assignment_scope(qs, request).order_by("-created_at")


def _filter_franchise_enquiry_qs(request):
    params = _query_params(request)
    source_filter = _request_source_filter(request)
    if not _include_franchise_enquiry(source_filter):
        return FranchiseEnquiry.objects.none()

    centre_ids = _request_centre_ids(request)
    if centre_ids:
        qs = FranchiseEnquiry.objects.filter(franchise_id__in=centre_ids)
    else:
        qs = FranchiseEnquiry.objects.filter(franchise__isnull=True)

    status_value = (params.get("status") or "").strip()
    if status_value:
        qs = qs.filter(status=status_value)

    search = (params.get("search") or "").strip()
    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
            | Q(city__icontains=search)
            | Q(message__icontains=search)
            | Q(franchise__name__icontains=search)
        )

    start, end = _parse_request_dates(request)
    if start:
        qs = qs.filter(created_at__gte=start)
    if end:
        qs = qs.filter(created_at__lte=end)

    state_value = (params.get("state") or "").strip()
    if state_value:
        from accounts.crm_zones import clamp_requested_states

        state_value = clamp_requested_states(request, state_value) or ""
        state_queries = Q()
        for s in [x.strip() for x in state_value.split(",") if x.strip()]:
            state_queries |= Q(state__iexact=s) | Q(franchise__state__iexact=s) | Q(franchise__statename__iexact=s)
        qs = qs.filter(state_queries)

    qs = _filter_qs_by_city(
        qs,
        request,
        field_name="city",
        franchise_city_fields=("franchise__city", "franchise__cityname"),
    )
    qs = _filter_enquiry_qs_by_centre(qs, request)
    qs = _apply_assigned_user_filter(qs, request)
    from accounts.crm_zones import filter_franchise_enquiry_qs_by_zone

    qs = filter_franchise_enquiry_qs_by_zone(qs, request)
    return _apply_viewer_assignment_scope(qs, request).order_by("-created_at")


def _apply_landing_zone_scope(qs, request):
    """Apply the viewer's state/city territory to landing leads."""
    from accounts.crm_zones import request_effective_scope_codes, scope_city_names, scope_match_values

    codes = request_effective_scope_codes(request)
    if codes is None:
        return qs
    zone_q = Q()
    for value in scope_match_values(codes):
        zone_q |= Q(state__iexact=value)
    for city_name in scope_city_names(codes):
        zone_q |= Q(city__iexact=city_name)
    return qs.filter(zone_q) if zone_q else qs.none()


def _filter_landing_qs(request):
    params = _query_params(request)
    if not _include_landing(_request_source_filter(request)):
        return KidsEnquiry.objects.none()

    qs = KidsEnquiry.objects.select_related("assigned_user")

    status_value = (params.get("status") or "").strip()
    if status_value:
        if status_value in ("new", "untouched"):
            qs = qs.filter(
                Q(raw_payload__crm_status__isnull=True)
                | Q(raw_payload__crm_status="")
                | Q(raw_payload__crm_status="new")
                | Q(raw_payload__crm_status="untouched")
            )
        else:
            qs = qs.filter(raw_payload__crm_status=status_value)

    search = (params.get("search") or "").strip()
    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(mobileno__icontains=search)
            | Q(mobile__icontains=search)
            | Q(email__icontains=search)
            | Q(city__icontains=search)
            | Q(state__icontains=search)
            | Q(location__icontains=search)
            | Q(centre_name__icontains=search)
        )

    start, end = _parse_request_dates(request)
    if start:
        qs = qs.filter(created_date__gte=start)
    if end:
        qs = qs.filter(created_date__lte=end)

    state_value = (params.get("state") or "").strip()
    if state_value:
        from accounts.crm_zones import clamp_requested_states

        state_value = clamp_requested_states(request, state_value) or ""
        state_queries = Q()
        for s in [x.strip() for x in state_value.split(",") if x.strip()]:
            state_queries |= Q(state__iexact=s)
        if state_queries:
            qs = qs.filter(state_queries)

    qs = _filter_landing_qs_by_city(qs, request)
    qs = _filter_landing_qs_by_centre(qs, request)

    qs = _apply_landing_zone_scope(qs, request)
    qs = _apply_assigned_user_filter(qs, request)
    return _apply_viewer_assignment_scope(qs, request).order_by("-created_date")


def unified_leads_total(request) -> int:
    total = 0
    if _include_crm(_request_source_filter(request)):
        total += _filter_crm_qs(request).count()
    if _include_admission(_request_source_filter(request)):
        total += _filter_enquiry_qs(request, EnquiryType.ADMISSION).count()
    if _include_contact(_request_source_filter(request)):
        total += _filter_enquiry_qs(request, EnquiryType.CONTACT).count()
    if _include_franchise_enquiry(_request_source_filter(request)):
        total += _filter_franchise_enquiry_qs(request).count()
    if _include_landing(_request_source_filter(request)):
        total += _filter_landing_qs(request).count()
    return total


def unified_leads_page(request, *, page: int, limit: int) -> list[dict]:
    offset = (page - 1) * limit
    fetch_count = offset + limit
    merged: list[dict] = []

    if _include_crm(_request_source_filter(request)):
        merged.extend(lead_to_dict(row) for row in _filter_crm_qs(request)[:fetch_count])
    if _include_admission(_request_source_filter(request)):
        merged.extend(
            enquiry_to_dict(row) for row in _filter_enquiry_qs(request, EnquiryType.ADMISSION)[:fetch_count]
        )
    if _include_contact(_request_source_filter(request)):
        merged.extend(
            enquiry_to_dict(row) for row in _filter_enquiry_qs(request, EnquiryType.CONTACT)[:fetch_count]
        )
    if _include_franchise_enquiry(_request_source_filter(request)):
        merged.extend(
            franchise_enquiry_to_dict(row) for row in _filter_franchise_enquiry_qs(request)[:fetch_count]
        )
    if _include_landing(_request_source_filter(request)):
        merged.extend(landing_to_dict(row) for row in _filter_landing_qs(request)[:fetch_count])

    merged.sort(key=lambda row: row.get("createdAt") or "", reverse=True)
    page_rows = merged[offset : offset + limit]
    if is_campaign_external_viewer(request=request):
        return [redact_lead_for_campaign_viewer(row) or row for row in page_rows]
    return page_rows


def unified_dashboard_stats(request) -> dict:
    today = timezone.localdate()
    source_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    today_count = 0
    follow_ups = 0
    converted = 0

    if _include_crm(_request_source_filter(request)):
        crm_qs = _filter_crm_qs(request)
        # Always break out campaign channels (website / fb / insta / LP / META)
        # so reports & charts can show each source separately.
        for row in crm_qs.values("source", "landing_page_url").annotate(count=Count("id")):
            api_source = (
                campaign_channel_api_key(row["source"], row.get("landing_page_url"))
                or source_to_api(row["source"])
            )
            source_counts[api_source] = source_counts.get(api_source, 0) + row["count"]
        for row in crm_qs.values("status").annotate(count=Count("id")):
            status_counts[row["status"]] = status_counts.get(row["status"], 0) + row["count"]
        today_count += crm_qs.filter(created_at__date=today).count()
        follow_ups += crm_qs.filter(
            status__in=[CrmLeadStatus.FOLLOW_UP, CrmLeadStatus.VISITED_SCHOOL]
        ).count()
        converted += crm_qs.filter(status=CrmLeadStatus.CONVERTED_ADMISSION).count()

    if _include_admission(_request_source_filter(request)):
        admission_qs = _filter_enquiry_qs(request, EnquiryType.ADMISSION)
        admission_count = admission_qs.count()
        if admission_count:
            source_counts["admission"] = source_counts.get("admission", 0) + admission_count
        for row in admission_qs.values("status").annotate(count=Count("id")):
            mapped = _enquiry_status_to_crm(row["status"])
            status_counts[mapped] = status_counts.get(mapped, 0) + row["count"]
        today_count += admission_qs.filter(created_at__date=today).count()
        follow_ups += admission_qs.filter(
            status__in=[CrmLeadStatus.FOLLOW_UP, CrmLeadStatus.VISITED_SCHOOL, "in-progress"]
        ).count()
        converted += admission_qs.filter(status__in=[CrmLeadStatus.CONVERTED_ADMISSION, "closed"]).count()

    if _include_contact(_request_source_filter(request)):
        contact_qs = _filter_enquiry_qs(request, EnquiryType.CONTACT)
        contact_count = contact_qs.count()
        if contact_count:
            source_counts["contact"] = source_counts.get("contact", 0) + contact_count
        for row in contact_qs.values("status").annotate(count=Count("id")):
            mapped = _enquiry_status_to_crm(row["status"])
            status_counts[mapped] = status_counts.get(mapped, 0) + row["count"]
        today_count += contact_qs.filter(created_at__date=today).count()
        follow_ups += contact_qs.filter(
            status__in=[CrmLeadStatus.FOLLOW_UP, CrmLeadStatus.VISITED_SCHOOL, "in-progress"]
        ).count()
        converted += contact_qs.filter(status__in=[CrmLeadStatus.CONVERTED_ADMISSION, "closed"]).count()

    if _include_franchise_enquiry(_request_source_filter(request)):
        franchise_qs = _filter_franchise_enquiry_qs(request)
        franchise_count = franchise_qs.count()
        if franchise_count:
            source_counts["franchise"] = source_counts.get("franchise", 0) + franchise_count
        for row in franchise_qs.values("status").annotate(count=Count("id")):
            status_counts[row["status"]] = status_counts.get(row["status"], 0) + row["count"]
        today_count += franchise_qs.filter(created_at__date=today).count()
        follow_ups += franchise_qs.filter(status__in=[CrmLeadStatus.FOLLOW_UP, CrmLeadStatus.HOT, CrmLeadStatus.WARM, CrmLeadStatus.COLD]).count()
        converted += franchise_qs.filter(status__in=[CrmLeadStatus.CONVERTED_MOU, CrmLeadStatus.CONVERTED_AGREEMENT]).count()

    if _include_landing(_request_source_filter(request)):
        landing_qs = _filter_landing_qs(request)
        landing_count = landing_qs.count()
        if landing_count:
            source_counts["landing"] = source_counts.get("landing", 0) + landing_count
        # Clear select_related before only() — assigned_user can't be deferred and joined.
        for row in landing_qs.select_related(None).only("raw_payload").iterator():
            mapped = _landing_crm_status(row)
            status_counts[mapped] = status_counts.get(mapped, 0) + 1
            if mapped in (CrmLeadStatus.FOLLOW_UP, CrmLeadStatus.VISITED_SCHOOL):
                follow_ups += 1
            if mapped == CrmLeadStatus.CONVERTED_ADMISSION:
                converted += 1
        today_count += landing_qs.filter(created_date__date=today).count()

    return {
        "totalEnquiries": unified_leads_total(request),
        "todayLeads": today_count,
        "followUps": follow_ups,
        "converted": converted,
        "sourceBreakdown": [
            {"source": source, "count": count}
            for source, count in sorted(source_counts.items(), key=lambda item: item[1], reverse=True)
        ],
        "statusBreakdown": [
            {"status": status, "count": count}
            for status, count in sorted(status_counts.items(), key=lambda item: item[1], reverse=True)
        ],
    }


def _get_reminders(qs, to_dict_func, updated_field="updated_at", status_field="status"):
    now = timezone.now()
    today = timezone.localdate()
    next_week = today + timedelta(days=7)
    closed = [
        CrmLeadStatus.CONVERTED_ADMISSION,
        CrmLeadStatus.CONVERTED_MOU,
        CrmLeadStatus.CONVERTED_AGREEMENT,
        CrmLeadStatus.NOT_INTERESTED,
        CrmLeadStatus.WRONG_ENQUIRY,
        "closed"
    ]

    meetings_qs = qs.filter(
        **{
            "meeting_date__isnull": False,
            "meeting_date__date__gte": today,
            "meeting_date__date__lte": next_week,
        }
    ).exclude(**{f"{status_field}__in": closed}).order_by("meeting_date")

    follow_ups_qs = qs.filter(
        **{
            "next_follow_up_date__isnull": False,
            "next_follow_up_date__date__gte": today,
            "next_follow_up_date__date__lte": next_week,
        }
    ).exclude(**{f"{status_field}__in": closed}).order_by("next_follow_up_date")

    return {
        "meetings": [to_dict_func(l) for l in meetings_qs[:50]],
        "followUps": [to_dict_func(l) for l in follow_ups_qs[:50]],
    }


def _request_for_reminders(request):
    """
    Reminders should use the same territory/source/city/user filters as the
    dashboard, but ignore created-at date range (upcoming follow-ups are
    independent of when the lead was created).
    """
    base = getattr(request, "query_params", None) or request.GET
    params = base.copy()
    params.pop("startDate", None)
    params.pop("endDate", None)
    request._reminders_query_params = params
    return request


def unified_reminders(request) -> dict:
    # Reuse the same scoped querysets as dashboard stats (zone/city/user/source).
    request = _request_for_reminders(request)
    source_filter = _request_source_filter(request)

    meetings = []
    follow_ups = []

    if not source_filter or _include_crm(source_filter):
        crm_qs = _filter_crm_qs(request)
        res = _get_reminders(crm_qs, lead_to_dict, "updated_at")
        meetings.extend(res["meetings"])
        follow_ups.extend(res["followUps"])

    if not source_filter or _include_admission(source_filter):
        enq_qs = _filter_enquiry_qs(request, EnquiryType.ADMISSION)
        res = _get_reminders(enq_qs, enquiry_to_dict, "created_at")
        meetings.extend(res["meetings"])
        follow_ups.extend(res["followUps"])

    if not source_filter or _include_contact(source_filter):
        enq_qs = _filter_enquiry_qs(request, EnquiryType.CONTACT)
        res = _get_reminders(enq_qs, enquiry_to_dict, "created_at")
        meetings.extend(res["meetings"])
        follow_ups.extend(res["followUps"])

    if not source_filter or _include_landing(source_filter):
        landing_qs = _filter_landing_qs(request)
        today = timezone.localdate()
        next_week = today + timedelta(days=7)
        # kids_enquiry has no status column (status lives in raw_payload)
        meetings.extend(
            landing_to_dict(row)
            for row in landing_qs.filter(
                meeting_date__isnull=False,
                meeting_date__date__gte=today,
                meeting_date__date__lte=next_week,
            ).order_by("meeting_date")[:50]
        )
        follow_ups.extend(
            landing_to_dict(row)
            for row in landing_qs.filter(
                next_follow_up_date__isnull=False,
                next_follow_up_date__date__gte=today,
                next_follow_up_date__date__lte=next_week,
            ).order_by("next_follow_up_date")[:50]
        )

    if not source_filter or _include_franchise_enquiry(source_filter):
        fe_qs = _filter_franchise_enquiry_qs(request)
        res = _get_reminders(fe_qs, franchise_enquiry_to_dict, "created_at")
        meetings.extend(res["meetings"])
        follow_ups.extend(res["followUps"])

    def _sort_meetings(m):
        return parse_datetime(m["meetingDate"] or "") or now()
    
    def _sort_followups(f):
        return parse_datetime(f["nextFollowUpDate"] or "") or parse_datetime(f["updatedAt"] or "") or now()

    from django.utils.dateparse import parse_datetime
    from django.utils.timezone import now

    meetings.sort(key=_sort_meetings)
    follow_ups.sort(key=_sort_followups)

    return {
        "meetings": meetings[:50],
        "followUps": follow_ups[:50]
    }


def _attach_viewer_flags(data: dict | None, request=None) -> dict | None:
    """Add viewer-specific flags (assign permission) for lead detail UI."""
    if not data:
        return data
    from .crm_users import user_can_assign_crm_leads

    viewer = getattr(request, "user", None) if request is not None else None
    if is_campaign_external_viewer(user=viewer):
        return redact_lead_for_campaign_viewer(data)
    data["canAssignUsers"] = user_can_assign_crm_leads(viewer)
    return data


def unified_lead_detail(raw_id: str, *, include_detail: bool = False, request=None) -> dict | None:
    kind, pk = parse_lead_id(raw_id)
    if request is not None:
        if is_agency_crm_user(request=request):
            if is_ants_agency_user(request=request):
                # Ants: West Bengal city landing pages only.
                if kind != "landing":
                    return None
            elif kind not in ("crm", "landing"):
                # Bcwebwise: Facebook/Meta campaign + city landing only.
                return None
        if is_campaign_only_crm_user(request=request) and kind != "crm":
            # Campaign-only login cannot open Admission/Contact/Franchise/Landing detail pages.
            return None
    if kind == "crm":
        qs = CrmLead.objects.filter(pk=pk).select_related("assigned_user").prefetch_related("notes")
        if request is not None:
            from accounts.crm_zones import filter_crm_lead_qs_by_zone

            qs = filter_crm_lead_qs_by_zone(qs, request)
            qs = _apply_viewer_assignment_scope(qs, request)
        lead = qs.first()
        if not lead:
            return None
        return _attach_viewer_flags(lead_to_dict(lead, include_detail=include_detail), request)
    if kind == "enquiry":
        qs = Enquiry.objects.select_related("franchise", "assigned_user").filter(pk=pk)
        if request is not None:
            from accounts.crm_zones import filter_enquiry_qs_by_zone

            qs = filter_enquiry_qs_by_zone(qs, request)
            qs = _apply_viewer_assignment_scope(qs, request)
        enquiry = qs.first()
        if not enquiry:
            return None
        return _attach_viewer_flags(enquiry_to_dict(enquiry, include_detail=include_detail), request)
    if kind == "franchiseenquiry":
        qs = FranchiseEnquiry.objects.select_related("franchise", "assigned_user").filter(pk=pk)
        if request is not None:
            from accounts.crm_zones import filter_franchise_enquiry_qs_by_zone

            qs = filter_franchise_enquiry_qs_by_zone(qs, request)
            qs = _apply_viewer_assignment_scope(qs, request)
        franchise_enq = qs.first()
        if not franchise_enq:
            return None
        return _attach_viewer_flags(
            franchise_enquiry_to_dict(franchise_enq, include_detail=include_detail), request
        )
    if kind == "landing":
        qs = KidsEnquiry.objects.select_related("assigned_user").filter(pk=pk)
        if request is not None:
            qs = _apply_landing_zone_scope(qs, request)
            qs = _apply_viewer_assignment_scope(qs, request)
        row = qs.first()
        return _attach_viewer_flags(
            landing_to_dict(row, include_detail=include_detail) if row else None, request
        )
    return None


def update_unified_lead(raw_id: str, data: dict, *, include_detail: bool = False, request=None) -> dict | None:
    # Block updates for leads outside the caller's CRM zone
    if request is not None and unified_lead_detail(raw_id, include_detail=False, request=request) is None:
        return None

    kind, numeric_id = parse_lead_id(raw_id)
    status = (data.get("status") or "").strip()
    if status and status not in _valid_crm_statuses():
        raise ValueError(f"Invalid status: {status}")

    if kind == "crm":
        lead = CrmLead.objects.filter(pk=numeric_id).prefetch_related("notes").first()
        if not lead:
            return None
        updates = parse_update_payload(data)
        if "status" in updates and updates["status"] not in _valid_crm_statuses():
            raise ValueError(f"Invalid status: {updates['status']}")
        for field, value in updates.items():
            setattr(lead, field, value)
        if "meetingDate" in data:
            lead.meeting_date = parse_datetime(data["meetingDate"]) if data["meetingDate"] else None
        if "nextFollowUpDate" in data:
            lead.next_follow_up_date = parse_datetime(data["nextFollowUpDate"]) if data["nextFollowUpDate"] else None
        assignment_changed = _maybe_assign_lead(lead, request, data)
        lead.save()
        if assignment_changed:
            _notify_explicit_assignment(lead, request)
        return _attach_viewer_flags(lead_to_dict(lead, include_detail=include_detail), request)

    if kind == "enquiry":
        enquiry = Enquiry.objects.select_related("franchise", "assigned_user").filter(pk=numeric_id).first()
        if not enquiry:
            return None
        if status:
            enquiry.status = _crm_status_to_enquiry(status)
        if "fullName" in data:
            enquiry.name = data["fullName"]
        if "email" in data:
            enquiry.email = data["email"]
        if "mobile" in data:
            enquiry.phone = data["mobile"]
        if "city" in data:
            enquiry.city = data["city"]
        if "comments" in data:
            enquiry.message = data["comments"]
        if "childAge" in data:
            enquiry.child_age = data["childAge"]
        if "meetingDate" in data:
            enquiry.meeting_date = parse_datetime(data["meetingDate"]) if data["meetingDate"] else None
        if "nextFollowUpDate" in data:
            enquiry.next_follow_up_date = parse_datetime(data["nextFollowUpDate"]) if data["nextFollowUpDate"] else None
        assignment_changed = _maybe_assign_lead(enquiry, request, data)
        enquiry.save()
        if assignment_changed:
            _notify_explicit_assignment(enquiry, request)
        # Do NOT cascade status to other rows from CRM. Updating one lead must
        # never change unrelated leads that happen to share a phone number.
        return _attach_viewer_flags(enquiry_to_dict(enquiry, include_detail=include_detail), request)

    if kind == "franchiseenquiry":
        franchise_enq = FranchiseEnquiry.objects.select_related("franchise", "assigned_user").filter(pk=numeric_id).first()
        if not franchise_enq:
            return None
        if status:
            franchise_enq.status = status
        if "fullName" in data:
            franchise_enq.name = data["fullName"]
        if "email" in data:
            franchise_enq.email = data["email"]
        if "mobile" in data:
            franchise_enq.phone = data["mobile"]
        if "city" in data:
            franchise_enq.city = data["city"]
        if "state" in data:
            franchise_enq.state = data["state"]
        if "comments" in data:
            franchise_enq.message = data["comments"]
        if "meetingDate" in data:
            franchise_enq.meeting_date = parse_datetime(data["meetingDate"]) if data["meetingDate"] else None
        if "nextFollowUpDate" in data:
            franchise_enq.next_follow_up_date = parse_datetime(data["nextFollowUpDate"]) if data["nextFollowUpDate"] else None
        assignment_changed = _maybe_assign_lead(franchise_enq, request, data)
        franchise_enq.save()
        if assignment_changed:
            _notify_explicit_assignment(franchise_enq, request)
        return _attach_viewer_flags(
            franchise_enquiry_to_dict(franchise_enq, include_detail=include_detail), request
        )

    if kind == "landing":
        row = KidsEnquiry.objects.select_related("assigned_user").filter(pk=numeric_id).first()
        if not row:
            return None
        if "fullName" in data:
            row.name = data["fullName"]
        if "email" in data:
            row.email = data["email"]
        if "mobile" in data:
            row.mobileno = data["mobile"]
        if "city" in data:
            row.city = data["city"]
        if "state" in data:
            row.state = data["state"]
        payload = dict(row.raw_payload) if isinstance(row.raw_payload, dict) else {}
        if status:
            payload["crm_status"] = status
        row.raw_payload = payload
        if "meetingDate" in data:
            row.meeting_date = parse_datetime(data["meetingDate"]) if data["meetingDate"] else None
        if "nextFollowUpDate" in data:
            row.next_follow_up_date = parse_datetime(data["nextFollowUpDate"]) if data["nextFollowUpDate"] else None
        assignment_changed = _maybe_assign_lead(row, request, data)
        row.save()
        if assignment_changed:
            _notify_explicit_assignment(row, request)
        return _attach_viewer_flags(landing_to_dict(row, include_detail=include_detail), request)

    return None


def apply_lead_filters(qs, request):
    source = normalize_source_from_api(request.query_params.get("source"))
    if source:
        qs = qs.filter(source=source)

    status_value = (request.query_params.get("status") or "").strip()
    if status_value:
        qs = qs.filter(status=status_value)

    search = (request.query_params.get("search") or "").strip()
    if search:
        qs = qs.filter(
            Q(full_name__icontains=search)
            | Q(mobile__icontains=search)
            | Q(email__icontains=search)
            | Q(city__icontains=search)
            | Q(state__icontains=search)
            | Q(preferred_centre_location__icontains=search)
        )

    raw_start = (request.query_params.get("startDate") or "").strip()
    raw_end = (request.query_params.get("endDate") or "").strip()
    start = parse_datetime(raw_start) or (parse_date(raw_start) if raw_start else None)
    end = parse_datetime(raw_end) or (parse_date(raw_end) if raw_end else None)
    if start:
        qs = qs.filter(created_at__gte=start)
    if end:
        qs = qs.filter(created_at__lte=end)
    return qs


def parse_update_payload(data: dict) -> dict:
    field_map = {
        "fullName": "full_name",
        "mobile": "mobile",
        "email": "email",
        "city": "city",
        "state": "state",
        "preferredCentreLocation": "preferred_centre_location",
        "franchiseType": "franchise_type",
        "investmentRange": "investment_range",
        "expectedStartDate": "expected_start_date",
        "comments": "comments",
        "status": "status",
    }
    out: dict = {}
    for api_key, model_key in field_map.items():
        if api_key in data:
            out[model_key] = data[api_key]
        elif model_key in data:
            out[model_key] = data[model_key]

    if "source" in data:
        out["source"] = normalize_source_from_api(data.get("source"))

    if "meetingDate" in data:
        raw = data.get("meetingDate")
        out["meeting_date"] = parse_datetime(raw) if raw else None
    if "nextFollowUpDate" in data:
        raw = data.get("nextFollowUpDate")
        out["next_follow_up_date"] = parse_datetime(raw) if raw else None

    return out


def dashboard_stats(qs):
    today = timezone.localdate()
    source_breakdown = [
        {"source": source_to_api(row["source"]), "count": row["count"]}
        for row in qs.values("source").annotate(count=Count("id")).order_by("-count")
    ]
    status_breakdown = [
        {"status": row["status"], "count": row["count"]}
        for row in qs.values("status").annotate(count=Count("id")).order_by("-count")
    ]
    return {
        "totalEnquiries": qs.count(),
        "todayLeads": qs.filter(created_at__date=today).count(),
        "followUps": qs.filter(status=CrmLeadStatus.FOLLOW_UP).count(),
        "converted": qs.filter(status=CrmLeadStatus.CONVERTED_ADMISSION).count(),
        "sourceBreakdown": source_breakdown,
        "statusBreakdown": status_breakdown,
    }

def unified_reports_data(request) -> dict:
    """Returns pivot data for the Reports View grouped by City, Source, and Status."""
    from accounts.crm_zones import request_scope_state_codes, scope_city_names
    from django.db.models import F, Value
    from django.db.models.functions import Coalesce, NullIf

    cities_data = {}
    params = _query_params(request)
    state_param = (params.get("state") or "").strip() or None
    requested_cities = [x.strip() for x in (_request_city_filter(request) or "").split(",") if x.strip()]
    codes = request_scope_state_codes(request)

    source_filter = _request_source_filter(request)

    if requested_cities:
        # Scoped CRM: never include cities outside the region/zone.
        if codes is not None:
            allowed = {c.casefold(): c for c in scope_city_names(codes, state_param)}
            requested_cities = [
                allowed.get(c.casefold(), c)
                for c in requested_cities
                if c.casefold() in allowed
            ]
    elif state_param:
        # State filter applied, City = All → full city list for that state (incl. empty).
        requested_cities = list(unified_crm_cities(state_param, request=request))
    else:
        # State + City = All → only cities that have leads (avoid dumping all-India zeros).
        requested_cities = []

    for rc in requested_cities:
        cities_data[rc] = {"admission": {}, "landing": {}, "contact": {}, "campaign": {}, "franchise": {}}

    scope_cities_cf = None
    if codes is not None:
        scope_cities_cf = {c.casefold() for c in scope_city_names(codes, state_param)}

    def _find_requested_city(db_city):
        if not db_city:
            return "Unknown"
        db_city_norm = db_city.strip().lower()

        from franchises.franchise_geo import city_query_variants
        for rc in requested_cities:
            variants = [v.lower() for v in city_query_variants(rc)]
            if db_city_norm in variants:
                return rc
        return db_city.strip().title()

    def _add_count(db_city, source, status, count):
        city = _find_requested_city(db_city)
        if city not in cities_data:
            if scope_cities_cf is not None and city.casefold() not in scope_cities_cf:
                return
            cities_data[city] = {"admission": {}, "landing": {}, "contact": {}, "campaign": {}, "franchise": {}}
        if source not in cities_data[city]:
            cities_data[city][source] = {}
        cities_data[city][source][status] = cities_data[city][source].get(status, 0) + count

    def _enquiry_report_city_expr():
        """Prefer enquiry.city; fall back to linked franchise city (common for admission/contact)."""
        return Coalesce(
            NullIf(F("city"), Value("")),
            NullIf(F("franchise__cityname"), Value("")),
            NullIf(F("franchise__city"), Value("")),
            Value("Unknown"),
        )

    # 1. Website admission (EnquiryType.ADMISSION)
    if _include_admission(source_filter):
        admission_qs = _filter_enquiry_qs(request, EnquiryType.ADMISSION).select_related("franchise").order_by()
        for row in (
            admission_qs.annotate(report_city=_enquiry_report_city_expr())
            .values("report_city", "status")
            .annotate(count=Count("id"))
        ):
            mapped_status = _enquiry_status_to_crm(row["status"])
            _add_count(row["report_city"], "admission", mapped_status, row["count"])

    # 2. Centerpage (EnquiryType.CONTACT)
    if _include_contact(source_filter):
        contact_qs = _filter_enquiry_qs(request, EnquiryType.CONTACT).select_related("franchise").order_by()
        for row in (
            contact_qs.annotate(report_city=_enquiry_report_city_expr())
            .values("report_city", "status")
            .annotate(count=Count("id"))
        ):
            mapped_status = _enquiry_status_to_crm(row["status"])
            _add_count(row["report_city"], "contact", mapped_status, row["count"])

    # 3. Campaign (CrmLead / campaign_leads)
    if not source_filter or _include_crm(source_filter):
        crm_qs = _filter_crm_qs(request).order_by()
        for row in crm_qs.values("city", "status", "source", "landing_page_url").annotate(count=Count("id")):
            api_src = (
                campaign_channel_api_key(row["source"], row.get("landing_page_url"))
                or source_to_api(row["source"])
                or "google"
            )
            if not source_filter:
                _add_count(row["city"], "campaign", row["status"], row["count"])
            elif source_filter in ("campaign", "franchise_all"):
                _add_count(row["city"], api_src, row["status"], row["count"])
                if source_filter == "campaign":
                    # Paid Campaign reports: channel breakdown + combined Campaign column.
                    _add_count(row["city"], "campaign", row["status"], row["count"])
            else:
                _add_count(row["city"], "campaign", row["status"], row["count"])

    # 4. Franchise (FranchiseEnquiry)
    if not source_filter or _include_franchise_enquiry(source_filter):
        franchise_qs = _filter_franchise_enquiry_qs(request).select_related("franchise").order_by()
        for row in (
            franchise_qs.annotate(report_city=_enquiry_report_city_expr())
            .values("report_city", "status")
            .annotate(count=Count("id"))
        ):
            _add_count(row["report_city"], "franchise", row["status"], row["count"])

    # 5. Landing (kids_enquiry) — city landing pages under Admission
    if _include_landing(source_filter):
        landing_qs = _filter_landing_qs(request).order_by()
        for row in landing_qs.values("city", "raw_payload").iterator():
            payload = row.get("raw_payload") if isinstance(row.get("raw_payload"), dict) else {}
            mapped_status = str(payload.get("crm_status") or "").strip() or "untouched"
            _add_count(row.get("city") or "Unknown", "landing", mapped_status, 1)

    return {"cities": cities_data}
