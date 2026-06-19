import json
from datetime import datetime

from rest_framework import serializers


def franchise_city_label(franchise) -> str:
    """City for a centre row — franchise.city with legacy cityname fallback."""
    if franchise is None:
        return ""
    try:
        from franchises.franchise_geo import effective_city

        return effective_city(franchise)
    except Exception:
        city = str(getattr(franchise, "city", None) or "").strip()
        cityname = str(getattr(franchise, "cityname", None) or "").strip()
        return city or cityname


def parse_holiday_entries(raw) -> list:
    if raw is None:
        return []
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise serializers.ValidationError({"holiday_entries": "Invalid holiday list data."}) from exc
    if not isinstance(raw, list):
        raise serializers.ValidationError({"holiday_entries": "Holiday list must be an array."})
    return raw


def _holiday_row_dict(row: dict, default_city: str = "") -> dict:
    city = str(row.get("city") or "").strip()
    if not city and default_city:
        city = default_city.strip()
    name = str(row.get("name") or row.get("holiday") or "").strip()
    date = str(row.get("date") or "").strip()[:10]
    return {"city": city, "name": name, "date": date}


def enrich_holiday_entries(raw, default_city: str | None = None) -> list:
    """API read: fill missing city on each row (does not change stored JSON by itself)."""
    default = (default_city or "").strip()
    out: list[dict] = []
    for row in raw or []:
        if not isinstance(row, dict):
            continue
        item = _holiday_row_dict(row, default)
        if item["name"] and item["date"]:
            out.append(item)
    return sorted(out, key=lambda item: item["date"])


def normalize_holiday_entries(raw, default_city: str | None = None) -> list:
    rows = parse_holiday_entries(raw)
    default = (default_city or "").strip()
    normalized: list[dict] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise serializers.ValidationError({"holiday_entries": f"Row {idx + 1} is invalid."})
        city = str(row.get("city") or "").strip()
        name = str(row.get("name") or row.get("holiday") or "").strip()
        date = str(row.get("date") or "").strip()[:10]
        if not name and not date and not city:
            continue
        if not name:
            raise serializers.ValidationError({"holiday_entries": f"Row {idx + 1}: holiday name is required."})
        if not date:
            raise serializers.ValidationError({"holiday_entries": f"Row {idx + 1}: date is required."})
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError as exc:
            raise serializers.ValidationError({"holiday_entries": f"Row {idx + 1}: use YYYY-MM-DD for date."}) from exc
        normalized.append(_holiday_row_dict(row, default))
    return sorted(normalized, key=lambda item: item["date"])


def merge_holiday_entries(
    global_rows,
    centre_rows,
    *,
    centre_default_city: str | None = None,
) -> list:
    """Parents: head-office base + centre additions/overrides (same date replaces HO row)."""
    centre_default = (centre_default_city or "").strip()
    by_date: dict[str, dict] = {}
    for row in global_rows or []:
        if isinstance(row, dict) and row.get("date"):
            by_date[str(row["date"])[:10]] = _holiday_row_dict(row, "")
    for row in centre_rows or []:
        if isinstance(row, dict) and row.get("date"):
            by_date[str(row["date"])[:10]] = _holiday_row_dict(row, centre_default)
    return sorted(by_date.values(), key=lambda item: item["date"])
