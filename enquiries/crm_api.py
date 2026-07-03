"""CRM admin API helpers — response shape matches timekids_crm_clone."""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from .models import CrmLead, CrmLeadNote, CrmLeadSource, CrmLeadStatus

CRM_SOURCE_FROM_API = {
    "website": CrmLeadSource.WEB,
    "facebook": CrmLeadSource.FB,
    "instagram": CrmLeadSource.INSTA,
    "web": CrmLeadSource.WEB,
    "fb": CrmLeadSource.FB,
    "insta": CrmLeadSource.INSTA,
}

CRM_SOURCE_TO_API = {
    CrmLeadSource.WEB: "website",
    CrmLeadSource.FB: "facebook",
    CrmLeadSource.INSTA: "instagram",
}


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


def lead_to_dict(lead: CrmLead, *, include_detail: bool = False) -> dict:
    data = {
        "id": str(lead.id),
        "fullName": lead.full_name,
        "mobile": lead.mobile,
        "email": lead.email or "",
        "city": lead.city or "",
        "state": lead.state or "",
        "preferredCentreLocation": lead.preferred_centre_location or "",
        "franchiseType": lead.franchise_type or None,
        "investmentRange": lead.investment_range or None,
        "expectedStartDate": lead.expected_start_date or None,
        "source": source_to_api(lead.source),
        "comments": lead.comments or "",
        "status": lead.status,
        "meetingDate": _dt(lead.meeting_date),
        "nextFollowUpDate": _dt(lead.next_follow_up_date),
        "createdAt": _dt(lead.created_at),
        "updatedAt": _dt(lead.updated_at),
    }
    if include_detail:
        data["notes"] = [note_to_dict(n) for n in lead.notes.all()]
        data["auditLogs"] = []
        data["notificationLogs"] = []
        data["callHistory"] = []
    return data


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
        "converted": qs.filter(status=CrmLeadStatus.CONVERTED).count(),
        "sourceBreakdown": source_breakdown,
        "statusBreakdown": status_breakdown,
    }


def reminders_for_qs(qs):
    now = timezone.now()
    today = timezone.localdate()
    next_week = today + timedelta(days=7)
    yesterday = now - timedelta(days=1)

    closed = [CrmLeadStatus.CONVERTED, CrmLeadStatus.DROPPED, CrmLeadStatus.NOT_INTERESTED]

    meetings_qs = qs.filter(
        status=CrmLeadStatus.MEETING_SCHEDULED,
        meeting_date__isnull=False,
        meeting_date__date__gte=today,
        meeting_date__date__lte=next_week,
    ).order_by("meeting_date")

    follow_ups_qs = qs.filter(
        (
            Q(next_follow_up_date__isnull=False, next_follow_up_date__lte=now)
            & ~Q(status__in=closed)
        )
        | (
            Q(next_follow_up_date__isnull=True, updated_at__lte=yesterday)
            & ~Q(status__in=closed)
            & ~Q(status=CrmLeadStatus.MEETING_SCHEDULED)
        )
    ).order_by("next_follow_up_date", "updated_at")

    return {
        "meetings": [lead_to_dict(l) for l in meetings_qs[:50]],
        "followUps": [lead_to_dict(l) for l in follow_ups_qs[:50]],
    }
