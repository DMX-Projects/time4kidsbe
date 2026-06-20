"""Mobile-friendly parent document list rows (Android/iOS parent app)."""

from __future__ import annotations

from documents.models import DocumentCategory


def _slice_date(value) -> str:
    raw = str(value or "").strip()
    return raw[:10] if raw else ""


def _row_has_file(row: dict) -> bool:
    return bool((row.get("file") or "").strip() or (row.get("file_view_path") or "").strip())


def _doc_updated_ts(row: dict) -> float:
    raw = row.get("updated_at") or row.get("created_at") or ""
    try:
        from django.utils.dateparse import parse_datetime

        parsed = parse_datetime(str(raw))
        if parsed is not None:
            return parsed.timestamp()
    except Exception:
        pass
    return 0.0


def _apply_open_fields(out: dict, row: dict) -> dict:
    pk = row.get("id")
    file_path = (row.get("file") or "").strip()
    video_embed = (row.get("video_embed_url") or "").strip()
    audio_file = (row.get("audio_file") or "").strip()
    audio_embed = (row.get("audio_embed_url") or "").strip()

    if video_embed and not file_path and not audio_file and not audio_embed:
        out["kind"] = "video"
        out["open_type"] = "embed"
        out["open_url"] = video_embed
    elif audio_file:
        out["kind"] = "audio"
        out["open_type"] = "stream"
        out["open_url"] = (row.get("audio_view_path") or "").strip() or (
            f"/documents/parent/documents/{pk}/audio/" if pk else ""
        )
    elif audio_embed:
        out["kind"] = "audio"
        out["open_type"] = "audio_embed"
        out["open_url"] = audio_embed
    elif file_path or (row.get("file_view_path") or "").strip():
        out["kind"] = "document"
        out["open_type"] = "stream"
        out["open_url"] = (row.get("file_view_path") or "").strip() or (
            f"/documents/parent/documents/{pk}/file/" if pk else ""
        )
    elif video_embed:
        out["kind"] = "video"
        out["open_type"] = "embed"
        out["open_url"] = video_embed
    else:
        out["kind"] = "document"
        out["open_type"] = "stream"
        out["open_url"] = ""

    out["has_media"] = bool((out.get("open_url") or "").strip())
    return out


def parent_document_mobile_row(row: dict) -> dict:
    """Full serializer row plus mobile open helpers and category-aware dates."""
    out = dict(row)
    category = str(row.get("category") or "").strip().upper()

    block = _slice_date(row.get("period_start"))
    uploaded = _slice_date(row.get("created_at"))
    updated = _slice_date(row.get("updated_at"))
    out["block_date"] = block or None
    out["uploaded_at"] = uploaded or None
    out["updated_on"] = updated or uploaded or None

    if category in (DocumentCategory.CLASS_TIMETABLE, DocumentCategory.NEWSLETTERS):
        out["date"] = block or uploaded
    elif category == DocumentCategory.PARENTING_TIPS:
        out["date"] = updated or uploaded
        subtitle = (row.get("description") or "").strip()
        out["subtitle"] = subtitle or None
    elif category == DocumentCategory.HOLIDAY_LISTS:
        out["date"] = updated or uploaded or None
        entries = row.get("holiday_entries") or []
        if not isinstance(entries, list):
            entries = []
        out["holiday_entries"] = entries
        out["holiday_count"] = len(entries)
        out["has_pdf"] = _row_has_file(row)
        out["source_type"] = "centre" if row.get("franchise") else "head_office"
    else:
        out["date"] = block or updated or uploaded

    subtitle = (row.get("description") or "").strip()
    if subtitle and "subtitle" not in out:
        out["subtitle"] = subtitle or None

    return _apply_open_fields(out, row)


def _merge_holiday_entries(rows: list[dict]) -> list[dict]:
    by_date: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        day = _slice_date(row.get("date"))
        if not day:
            continue
        by_date[day] = {
            "date": day,
            "name": str(row.get("name") or "").strip(),
            "city": str(row.get("city") or "").strip(),
        }
    return [by_date[k] for k in sorted(by_date.keys())]


def build_holiday_list_cards(serializer_data: list) -> list[dict]:
    """Group HO + centre holiday docs by state/academic year (matches parent web UI)."""
    by_key: dict[str, list[dict]] = {}
    standalone: list[dict] = []

    for row in serializer_data:
        state = str(row.get("state") or "").strip()
        year = str(row.get("academic_year") or "").strip()
        key = f"{state}|{year}"
        has_key = bool(state or year)
        entries = row.get("holiday_entries") or []
        if not isinstance(entries, list):
            entries = []
        if not has_key:
            if _row_has_file(row) or entries:
                standalone.append(row)
            continue
        bucket = by_key.get(key) or []
        bucket.append(row)
        by_key[key] = bucket

    cards: list[dict] = []

    for key, group in by_key.items():
        display = max(group, key=_doc_updated_ts)
        merged_entries: list[dict] = []
        pdf_downloads: list[dict] = []
        for doc in sorted(group, key=_doc_updated_ts, reverse=True):
            merged_entries.extend(doc.get("holiday_entries") or [])
            if _row_has_file(doc):
                mobile = parent_document_mobile_row(doc)
                is_centre = bool(doc.get("franchise"))
                pdf_downloads.append(
                    {
                        "document_id": doc.get("id"),
                        "source_type": "centre" if is_centre else "head_office",
                        "source_name": (
                            (doc.get("franchise_name") or doc.get("source_label") or "Your centre").strip()
                            if is_centre
                            else "Head office"
                        ),
                        "title": doc.get("display_title") or doc.get("title") or "Holiday list",
                        "open_url": mobile.get("open_url") or "",
                        "open_type": mobile.get("open_type") or "stream",
                        "has_pdf": True,
                    }
                )
        pdf_downloads.sort(key=lambda item: 0 if item.get("source_type") == "head_office" else 1)
        state, year = key.split("|", 1)
        cards.append(
            {
                "id": key,
                "label": display.get("display_title") or display.get("title") or "Holiday list",
                "state": state or None,
                "state_display": display.get("state_display"),
                "academic_year": year or None,
                "holiday_entries": _merge_holiday_entries(merged_entries),
                "holiday_count": len(_merge_holiday_entries(merged_entries)),
                "pdf_downloads": pdf_downloads,
                "has_pdf": bool(pdf_downloads),
            }
        )

    for doc in standalone:
        mobile = parent_document_mobile_row(doc)
        entries = doc.get("holiday_entries") or []
        if not isinstance(entries, list):
            entries = []
        is_centre = bool(doc.get("franchise"))
        pdf_downloads = []
        if _row_has_file(doc):
            pdf_downloads.append(
                {
                    "document_id": doc.get("id"),
                    "source_type": "centre" if is_centre else "head_office",
                    "source_name": (
                        (doc.get("franchise_name") or doc.get("source_label") or "Your centre").strip()
                        if is_centre
                        else "Head office"
                    ),
                    "title": doc.get("display_title") or doc.get("title") or "Holiday list",
                    "open_url": mobile.get("open_url") or "",
                    "open_type": mobile.get("open_type") or "stream",
                    "has_pdf": True,
                }
            )
        cards.append(
            {
                "id": str(doc.get("id")),
                "label": doc.get("display_title") or doc.get("title") or "Holiday list",
                "state": doc.get("state"),
                "state_display": doc.get("state_display"),
                "academic_year": doc.get("academic_year"),
                "holiday_entries": _merge_holiday_entries(entries),
                "holiday_count": len(_merge_holiday_entries(entries)),
                "pdf_downloads": pdf_downloads,
                "has_pdf": bool(pdf_downloads),
            }
        )

    cards.sort(key=lambda item: str(item.get("label") or "").lower())
    return cards


def parent_holiday_lists_api_response(request, serializer_data: list) -> dict | list:
    wrap = (request.query_params.get("wrap") or "").strip().lower()
    detail = (request.query_params.get("detail") or "").strip().lower()
    if wrap == "list" or detail in ("1", "true", "yes"):
        return serializer_data
    documents = [parent_document_mobile_row(row) for row in serializer_data]
    cards = build_holiday_list_cards(serializer_data)
    return {
        "holiday_lists": cards,
        "documents": documents,
        "count": len(documents),
    }


def parent_parental_tips_api_response(request, serializer_data: list) -> dict | list:
    wrap = (request.query_params.get("wrap") or "").strip().lower()
    detail = (request.query_params.get("detail") or "").strip().lower()
    if wrap == "list" or detail in ("1", "true", "yes"):
        return serializer_data
    tips = [parent_document_mobile_row(row) for row in serializer_data]
    return {
        "parental_tips": tips,
        "documents": tips,
        "count": len(tips),
    }


def parent_documents_api_response(request, serializer_data: list) -> dict | list:
    """
    Default: mobile envelope ``{ documents, count }``.
    ``?wrap=list`` or ``?detail=1``: bare full-serializer array (legacy web).
    """
    wrap = (request.query_params.get("wrap") or "").strip().lower()
    detail = (request.query_params.get("detail") or "").strip().lower()
    if wrap == "list" or detail in ("1", "true", "yes"):
        return serializer_data
    rows = [parent_document_mobile_row(row) for row in serializer_data]
    return {"documents": rows, "count": len(rows)}


def category_documents_api_response(request, category: str, serializer_data: list) -> dict | list:
    cat = (category or "").strip().upper()
    if cat == DocumentCategory.HOLIDAY_LISTS:
        return parent_holiday_lists_api_response(request, serializer_data)
    if cat == DocumentCategory.PARENTING_TIPS:
        return parent_parental_tips_api_response(request, serializer_data)
    return parent_documents_api_response(request, serializer_data)
