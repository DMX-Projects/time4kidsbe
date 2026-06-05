import json
from datetime import datetime

from rest_framework import serializers


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


def normalize_holiday_entries(raw) -> list:
    rows = parse_holiday_entries(raw)
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
        normalized.append({"city": city, "name": name, "date": date})
    return sorted(normalized, key=lambda item: item["date"])


def merge_holiday_entries(global_rows, centre_rows) -> list:
    """Parents: head-office base + centre additions/overrides (same date replaces HO row)."""
    by_date: dict[str, dict] = {}
    for row in global_rows or []:
        if isinstance(row, dict) and row.get("date"):
            by_date[str(row["date"])[:10]] = {
                "city": str(row.get("city") or "").strip(),
                "name": str(row.get("name") or row.get("holiday") or "").strip(),
                "date": str(row["date"])[:10],
            }
    for row in centre_rows or []:
        if isinstance(row, dict) and row.get("date"):
            by_date[str(row["date"])[:10]] = {
                "city": str(row.get("city") or "").strip(),
                "name": str(row.get("name") or row.get("holiday") or "").strip(),
                "date": str(row["date"])[:10],
            }
    return sorted(by_date.values(), key=lambda item: item["date"])
