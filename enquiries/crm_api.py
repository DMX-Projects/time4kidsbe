"""CRM admin API helpers — response shape matches timekids_crm_clone."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from .models import CrmLead, CrmLeadNote, CrmLeadSource, CrmLeadStatus, Enquiry, EnquiryType, KidsEnquiry, FranchiseEnquiry

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
        "expectedStartDate": lead.expected_start_date or None,
        "source": source_to_api(lead.source),
        "landingPageUrl": lead.landing_page_url or "",
        "pageType": (lead.utm_source or source_to_api(lead.source) or ""),
        "campaign": lead.utm_campaign or "",
        "utmSource": lead.utm_source or "",
        "utmMedium": lead.utm_medium or "",
        "utmCampaign": lead.utm_campaign or "",
        "comments": lead.comments or "",
        "status": lead.status,
        "meetingDate": _dt(lead.meeting_date),
        "nextFollowUpDate": _dt(lead.next_follow_up_date),
        "createdAt": _dt(lead.created_at),
        "updatedAt": _dt(lead.updated_at),
    }
    if include_detail:
        legacy_notes = [note_to_dict(n) for n in lead.notes.all()]
        new_notes = _get_unified_notes("crm", lead.id)
        data["notes"] = legacy_notes + new_notes
        data["auditLogs"] = []
        data["notificationLogs"] = []
        data["callHistory"] = []
    return data


def _query_params(request):
    return getattr(request, "query_params", None) or request.GET


def _parse_request_dates(request):
    params = _query_params(request)
    raw_start = (params.get("startDate") or "").strip()
    raw_end = (params.get("endDate") or "").strip()
    start = parse_datetime(raw_start) or (parse_date(raw_start) if raw_start else None)
    end = parse_datetime(raw_end) or (parse_date(raw_end) if raw_end else None)
    return start, end


def _request_centre_ids(request) -> list[int]:
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
        filter_franchise_qs_by_zone,
        request_scope_state_codes,
        scope_city_names,
    )

    codes = request_scope_state_codes(request) if request is not None else None
    # Scoped CRM (zone or region): return full city master list for that scope.
    if codes is not None:
        state_scoped = clamp_requested_states(request, state) if request is not None else state
        return scope_city_names(codes, state_scoped)

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
    return (_query_params(request).get("source") or "").strip().lower() or None


def _include_crm(source_filter: str | None) -> bool:
    if not source_filter:
        return True
    if source_filter == "campaign":
        return True
    return source_filter in {
        "website", "facebook", "instagram", "web", "fb", "insta",
        "july_lp", "july-lp", "july_meta", "july-meta", "lp_wb", "lp-wb",
    }


def _include_franchise_enquiry(source_filter: str | None) -> bool:
    return not source_filter or source_filter == "franchise"


def _include_admission(source_filter: str | None) -> bool:
    return not source_filter or source_filter == "admission"


def _include_contact(source_filter: str | None) -> bool:
    return not source_filter or source_filter == "contact"


def _include_landing(source_filter: str | None) -> bool:
    """``kids_enquiry`` landing leads use the separate landing-leads report, not unified CRM."""
    return False


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
    }
    if include_detail:
        data["notes"] = _get_unified_notes("enquiry", enquiry.id)
        data["auditLogs"] = []
        data["notificationLogs"] = []
        data["callHistory"] = []
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
    }
    if include_detail:
        data["notes"] = _get_unified_notes("franchiseenquiry", enquiry.id)
        data["auditLogs"] = []
        data["notificationLogs"] = []
        data["callHistory"] = []
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
    }
    if include_detail:
        data["notes"] = _get_unified_notes("landing", row.id)
        data["auditLogs"] = []
        data["notificationLogs"] = []
        data["callHistory"] = []
        data["centrePhone"] = centre_phone
        data["centreEmail"] = centre_email
    return data


def parse_lead_id(raw_id: str) -> tuple[str, int]:
    value = str(raw_id or "").strip()
    if "-" in value:
        kind, pk = value.split("-", 1)
        return kind.lower(), int(pk)
    return "crm", int(value)


def _filter_crm_qs(request):
    params = _query_params(request)
    qs = CrmLead.objects.all()
    source_filter = _request_source_filter(request)
    if source_filter and _include_crm(source_filter):
        if source_filter != "campaign":
            mapped = normalize_source_from_api(source_filter)
            if mapped in {
                CrmLeadSource.WEB,
                CrmLeadSource.FB,
                CrmLeadSource.INSTA,
                CrmLeadSource.JULY_LP,
                CrmLeadSource.JULY_META,
                CrmLeadSource.LP_WB,
            }:
                qs = qs.filter(source=mapped)
    elif source_filter and not _include_crm(source_filter):
        return CrmLead.objects.none()

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
    from accounts.crm_zones import filter_crm_lead_qs_by_zone

    return filter_crm_lead_qs_by_zone(qs, request).order_by("-created_at")


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
    from accounts.crm_zones import filter_enquiry_qs_by_zone

    return filter_enquiry_qs_by_zone(qs, request).order_by("-created_at")


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
    from accounts.crm_zones import filter_franchise_enquiry_qs_by_zone

    return filter_franchise_enquiry_qs_by_zone(qs, request).order_by("-created_at")


def _filter_landing_qs(request):
    params = _query_params(request)
    if not _include_landing(_request_source_filter(request)):
        return KidsEnquiry.objects.none()

    qs = KidsEnquiry.objects.all()

    status_value = (params.get("status") or "").strip()
    if status_value:
        if status_value == "new":
            qs = qs.filter(
                Q(raw_payload__crm_status__isnull=True)
                | Q(raw_payload__crm_status="")
                | Q(raw_payload__crm_status="new")
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

    qs = _filter_landing_qs_by_city(qs, request)
    qs = _filter_landing_qs_by_centre(qs, request)
    return qs.order_by("-created_date")


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
    return merged[offset : offset + limit]


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
        for row in crm_qs.values("source").annotate(count=Count("id")):
            api_source = source_to_api(row["source"])
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
        for row in landing_qs.only("raw_payload").iterator():
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


def unified_reminders(request) -> dict:
    source_filter = _request_source_filter(request)
    
    meetings = []
    follow_ups = []

    if not source_filter or _include_crm(source_filter):
        crm_qs = _filter_crm_qs(request)
        res = _get_reminders(crm_qs, lead_to_dict, "updated_at")
        meetings.extend(res["meetings"])
        follow_ups.extend(res["followUps"])

    if not source_filter or _include_admission(source_filter) or _include_contact(source_filter):
        enq_qs = Enquiry.objects.filter(enquiry_type__in=[EnquiryType.ADMISSION, EnquiryType.CONTACT])
        enq_qs = _filter_qs_by_city(enq_qs, request, field_name="city", franchise_city_fields=("franchise__city", "franchise__cityname"))
        enq_qs = _filter_enquiry_qs_by_centre(enq_qs, request)
        if source_filter:
            if _include_admission(source_filter) and not _include_contact(source_filter):
                enq_qs = enq_qs.filter(enquiry_type=EnquiryType.ADMISSION)
            elif _include_contact(source_filter) and not _include_admission(source_filter):
                enq_qs = enq_qs.filter(enquiry_type=EnquiryType.CONTACT)
        res = _get_reminders(enq_qs, enquiry_to_dict, "created_at")
        meetings.extend(res["meetings"])
        follow_ups.extend(res["followUps"])

    if not source_filter or _include_franchise_enquiry(source_filter):
        fe_qs = FranchiseEnquiry.objects.all()
        fe_qs = _filter_qs_by_city(fe_qs, request, field_name="city", franchise_city_fields=("franchise__city", "franchise__cityname"))
        fe_qs = _filter_enquiry_qs_by_centre(fe_qs, request)
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


def unified_lead_detail(raw_id: str, *, include_detail: bool = False, request=None) -> dict | None:
    kind, pk = parse_lead_id(raw_id)
    if kind == "crm":
        qs = CrmLead.objects.filter(pk=pk).prefetch_related("notes")
        if request is not None:
            from accounts.crm_zones import filter_crm_lead_qs_by_zone

            qs = filter_crm_lead_qs_by_zone(qs, request)
        lead = qs.first()
        return lead_to_dict(lead, include_detail=include_detail) if lead else None
    if kind == "enquiry":
        qs = Enquiry.objects.select_related("franchise").filter(pk=pk)
        if request is not None:
            from accounts.crm_zones import filter_enquiry_qs_by_zone

            qs = filter_enquiry_qs_by_zone(qs, request)
        enquiry = qs.first()
        return enquiry_to_dict(enquiry, include_detail=include_detail) if enquiry else None
    if kind == "franchiseenquiry":
        qs = FranchiseEnquiry.objects.select_related("franchise").filter(pk=pk)
        if request is not None:
            from accounts.crm_zones import filter_franchise_enquiry_qs_by_zone

            qs = filter_franchise_enquiry_qs_by_zone(qs, request)
        franchise_enq = qs.first()
        return franchise_enquiry_to_dict(franchise_enq, include_detail=include_detail) if franchise_enq else None
    if kind == "landing":
        row = KidsEnquiry.objects.filter(pk=pk).first()
        return landing_to_dict(row, include_detail=include_detail) if row else None
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
        lead.save()
        return lead_to_dict(lead, include_detail=include_detail)

    if kind == "enquiry":
        enquiry = Enquiry.objects.select_related("franchise").filter(pk=numeric_id).first()
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
        enquiry.save()
        from .views import _sync_enquiry_status_siblings
        _sync_enquiry_status_siblings(enquiry, enquiry.status)
        return enquiry_to_dict(enquiry, include_detail=include_detail)

    if kind == "franchiseenquiry":
        franchise_enq = FranchiseEnquiry.objects.select_related("franchise").filter(pk=numeric_id).first()
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
        franchise_enq.save()
        return franchise_enquiry_to_dict(franchise_enq, include_detail=include_detail)

    if kind == "landing":
        row = KidsEnquiry.objects.filter(pk=numeric_id).first()
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
        row.save()
        return landing_to_dict(row, include_detail=include_detail)

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

    cities_data = {}
    
    requested_cities = [x.strip() for x in (_request_city_filter(request) or "").split(",") if x.strip()]

    # Scoped CRM: never include cities outside the region/zone.
    codes = request_scope_state_codes(request)
    if codes is not None:
        allowed = {c.casefold(): c for c in scope_city_names(codes)}
        if requested_cities:
            requested_cities = [
                allowed.get(c.casefold(), c)
                for c in requested_cities
                if c.casefold() in allowed
            ]
        if not requested_cities:
            requested_cities = list(allowed.values())
    
    for rc in requested_cities:
        cities_data[rc] = {"admission": {}, "contact": {}, "campaign": {}, "franchise": {}}
        
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
            # Scoped reports stay on the scope city list — never expand outside
            if codes is not None:
                return
            cities_data[city] = {"admission": {}, "contact": {}, "campaign": {}, "franchise": {}}
        if source not in cities_data[city]:
            cities_data[city][source] = {}
        cities_data[city][source][status] = cities_data[city][source].get(status, 0) + count

    # 1. Admission (EnquiryType.ADMISSION)
    admission_qs = _filter_enquiry_qs(request, EnquiryType.ADMISSION)
    for row in admission_qs.values("city", "status").annotate(count=Count("id")):
        mapped_status = _enquiry_status_to_crm(row["status"])
        _add_count(row["city"], "admission", mapped_status, row["count"])

    # 2. Contact (EnquiryType.CONTACT - CenterPage)
    contact_qs = _filter_enquiry_qs(request, EnquiryType.CONTACT)
    for row in contact_qs.values("city", "status").annotate(count=Count("id")):
        mapped_status = _enquiry_status_to_crm(row["status"])
        _add_count(row["city"], "contact", mapped_status, row["count"])

    # 3. Campaign (CrmLead / campaign_leads) — bucket by channel so LP / META
    # show separately from Website / Facebook / Instagram.
    crm_qs = _filter_crm_qs(request)
    source_filter = _request_source_filter(request)
    for row in crm_qs.values("city", "status", "source").annotate(count=Count("id")):
        api_src = source_to_api(row["source"]) or "website"
        if not source_filter:
            # All Leads report: keep a single Campaign column (sum of channels)
            _add_count(row["city"], "campaign", row["status"], row["count"])
        elif source_filter == "campaign":
            # Campaign + All Channels: one column group per channel
            _add_count(row["city"], api_src, row["status"], row["count"])
        else:
            # Specific channel (website / july_lp / july_meta / …):
            # store under "campaign" so the UI can label it as that channel only
            _add_count(row["city"], "campaign", row["status"], row["count"])

    # 4. Franchise (FranchiseEnquiry)
    franchise_qs = _filter_franchise_enquiry_qs(request)
    for row in franchise_qs.values("city", "status").annotate(count=Count("id")):
        _add_count(row["city"], "franchise", row["status"], row["count"])

    return {"cities": cities_data}
