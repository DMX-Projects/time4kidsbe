"""Attendance resolution: holidays, unmarked days, and percentage calculation."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any

from documents.holiday_entries import franchise_city_label, merge_holiday_entries
from documents.models import DocumentCategory, ParentDocument
from documents.publish_targeting import document_matches_franchise

from .models import AttendanceRecord, CentreAttendanceClosedDay, StudentProfile

PRESENT_STATUSES = frozenset(
    {
        AttendanceRecord.Status.PRESENT,
        AttendanceRecord.Status.LATE,
    }
)
ABSENT_STATUSES = frozenset(
    {
        AttendanceRecord.Status.ABSENT,
        AttendanceRecord.Status.EXCUSED,
    }
)
RESOLVED_PRESENT = "PRESENT"
RESOLVED_ABSENT = "ABSENT"
RESOLVED_UNMARKED = "UNMARKED"
RESOLVED_HOLIDAY = "HOLIDAY"


def month_bounds(month_str: str) -> tuple[date | None, date | None]:
    """``YYYY-MM`` → (first day, last day) inclusive."""
    parts = (month_str or "").strip().split("-")
    if len(parts) != 2:
        return None, None
    try:
        year_i = int(parts[0])
        mon_i = int(parts[1])
        if mon_i < 1 or mon_i > 12:
            return None, None
        start = date(year_i, mon_i, 1)
        last_day = calendar.monthrange(year_i, mon_i)[1]
        end = date(year_i, mon_i, last_day)
        return start, end
    except (TypeError, ValueError):
        return None, None


def iter_days(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _normalize_city(value: str) -> str:
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


def _weekend_label(day: date) -> str:
    return "Sunday" if day.weekday() == 6 else "Saturday"


def is_weekend(day: date) -> bool:
    return day.weekday() >= 5


def _holiday_entry_applies(entry: dict, centre_city: str) -> bool:
    entry_city = (entry.get("city") or "").strip()
    if not entry_city:
        return True
    if not centre_city:
        return True
    return _normalize_city(entry_city) == _normalize_city(centre_city)


def _merged_holiday_entries_for_franchise(franchise) -> list[dict]:
    if franchise is None:
        return []
    qs = ParentDocument.objects.filter(
        is_active=True,
        category=DocumentCategory.HOLIDAY_LISTS,
    ).select_related("franchise")
    global_rows: list = []
    centre_rows: list = []
    for doc in qs:
        if doc.franchise_id:
            if doc.franchise_id != franchise.id:
                continue
            centre_rows.extend(doc.holiday_entries or [])
        elif document_matches_franchise(doc, franchise):
            global_rows.extend(doc.holiday_entries or [])
    return merge_holiday_entries(
        global_rows,
        centre_rows,
        centre_default_city=franchise_city_label(franchise) or None,
    )


def collect_holiday_map(franchise, start: date, end: date) -> dict[date, str]:
    """Dates treated as holidays (weekends, CMS calendar, centre closed days)."""
    labels: dict[date, str] = {}
    centre_city = franchise_city_label(franchise) if franchise else ""

    for entry in _merged_holiday_entries_for_franchise(franchise):
        if not isinstance(entry, dict):
            continue
        if not _holiday_entry_applies(entry, centre_city):
            continue
        raw = str(entry.get("date") or "")[:10]
        if len(raw) != 10:
            continue
        try:
            year_i, mon_i, day_i = (int(raw[0:4]), int(raw[5:7]), int(raw[8:10]))
            holiday_day = date(year_i, mon_i, day_i)
        except (TypeError, ValueError):
            continue
        if start <= holiday_day <= end:
            name = (entry.get("name") or entry.get("holiday") or "Holiday").strip() or "Holiday"
            labels[holiday_day] = name

    if franchise is not None:
        for row in CentreAttendanceClosedDay.objects.filter(
            franchise=franchise,
            date__gte=start,
            date__lte=end,
        ).only("date", "label"):
            labels[row.date] = (row.label or "Centre closed").strip() or "Centre closed"

    for day in iter_days(start, end):
        if is_weekend(day) and day not in labels:
            labels[day] = _weekend_label(day)

    return labels


def holiday_dates_payload(holiday_map: dict[date, str]) -> list[dict[str, str]]:
    return [
        {"date": day.isoformat(), "label": label}
        for day, label in sorted(holiday_map.items(), key=lambda item: item[0])
    ]


def normalize_record_status(raw: str | None) -> str | None:
    value = (raw or "").strip().upper()
    if not value:
        return None
    if value in PRESENT_STATUSES:
        return RESOLVED_PRESENT
    if value in ABSENT_STATUSES:
        return RESOLVED_ABSENT
    if value == AttendanceRecord.Status.HOLIDAY:
        return RESOLVED_HOLIDAY
    return value


def resolve_day_status(
    day: date,
    *,
    record_status: str | None = None,
    holiday_map: dict[date, str] | None = None,
) -> str:
    if holiday_map and day in holiday_map:
        return RESOLVED_HOLIDAY
    normalized = normalize_record_status(record_status)
    if normalized in (RESOLVED_PRESENT, RESOLVED_ABSENT, RESOLVED_HOLIDAY):
        return normalized
    return RESOLVED_UNMARKED


def compute_attendance_summary(
    *,
    start: date,
    end: date,
    records_by_date: dict[date, str],
    holiday_map: dict[date, str],
) -> dict[str, Any]:
    present = absent = unmarked = holiday = 0
    for day in iter_days(start, end):
        record_status = records_by_date.get(day)
        resolved = resolve_day_status(day, record_status=record_status, holiday_map=holiday_map)
        if resolved == RESOLVED_PRESENT:
            present += 1
        elif resolved == RESOLVED_ABSENT:
            absent += 1
        elif resolved == RESOLVED_HOLIDAY:
            holiday += 1
        else:
            unmarked += 1

    total_days = (end - start).days + 1
    marked_days = present + absent
    attendance_percentage = round((present / marked_days) * 100, 1) if marked_days else None

    return {
        "total_days": total_days,
        "present": present,
        "absent": absent,
        "unmarked": unmarked,
        "holiday": holiday,
        "marked_days": marked_days,
        "working_days": total_days - holiday,
        "attendance_percentage": attendance_percentage,
    }


def records_by_date_for_student(student: StudentProfile, start: date, end: date) -> dict[date, str]:
    rows = AttendanceRecord.objects.filter(
        student=student,
        date__gte=start,
        date__lte=end,
    ).values_list("date", "status")
    return {row_date: status for row_date, status in rows}


def build_month_summary_for_student(
    student: StudentProfile,
    franchise,
    month_str: str,
) -> dict[str, Any] | None:
    start, end = month_bounds(month_str)
    if start is None or end is None:
        return None
    holiday_map = collect_holiday_map(franchise, start, end)
    records = records_by_date_for_student(student, start, end)
    summary = compute_attendance_summary(
        start=start,
        end=end,
        records_by_date=records,
        holiday_map=holiday_map,
    )
    summary["month"] = month_str
    return summary


def build_summaries_for_student(
    student: StudentProfile,
    franchise,
    *,
    months: list[str] | None = None,
    records: list[dict] | None = None,
) -> dict[str, dict[str, Any]]:
    """Month-keyed summaries derived from attendance rows when months not supplied."""
    month_keys: set[str] = set(months or [])
    if records:
        for row in records:
            raw = str(row.get("date") or "")[:10]
            if len(raw) >= 7:
                month_keys.add(raw[:7])
    if not month_keys:
        month_keys.add(date.today().strftime("%Y-%m"))

    out: dict[str, dict[str, Any]] = {}
    for month_key in sorted(month_keys, reverse=True):
        summary = build_month_summary_for_student(student, franchise, month_key)
        if summary:
            out[month_key] = summary
    return out


def resolved_attendance_row(
    student: StudentProfile,
    day: date,
    *,
    record: AttendanceRecord | dict | None = None,
    holiday_map: dict[date, str],
) -> dict[str, Any]:
    record_status = None
    note = ""
    row_id = None
    if isinstance(record, AttendanceRecord):
        record_status = record.status
        note = record.note or ""
        row_id = record.pk
    elif isinstance(record, dict):
        record_status = record.get("status")
        note = (record.get("note") or "").strip()
        row_id = record.get("id")

    resolved = resolve_day_status(day, record_status=record_status, holiday_map=holiday_map)
    payload: dict[str, Any] = {
        "id": row_id,
        "student": student.pk,
        "student_id": student.pk,
        "student_name": student.full_name,
        "class_name": (student.class_name or "").strip(),
        "date": day.isoformat(),
        "status": resolved,
        "resolved_status": resolved,
        "note": note,
        "is_holiday": resolved == RESOLVED_HOLIDAY,
        "holiday_label": holiday_map.get(day, ""),
    }
    if record_status and normalize_record_status(record_status) != resolved:
        payload["saved_status"] = record_status
    return payload


def day_is_holiday(franchise, day: date) -> tuple[bool, str]:
    holiday_map = collect_holiday_map(franchise, day, day)
    if day in holiday_map:
        return True, holiday_map[day]
    return False, ""
