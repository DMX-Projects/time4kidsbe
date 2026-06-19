"""Mobile-friendly parent document list rows (Android/iOS parent app)."""

from __future__ import annotations


def _slice_date(value) -> str:
    raw = str(value or "").strip()
    return raw[:10] if raw else ""


def parent_document_mobile_row(row: dict) -> dict:
    """Full serializer row plus ``kind``, ``open_type``, ``open_url``, ``date``, ``has_media``."""
    out = dict(row)
    pk = row.get("id")
    file_path = (row.get("file") or "").strip()
    video_embed = (row.get("video_embed_url") or "").strip()
    audio_file = (row.get("audio_file") or "").strip()
    audio_embed = (row.get("audio_embed_url") or "").strip()

    block = _slice_date(row.get("period_start"))
    uploaded = _slice_date(row.get("created_at"))
    out["block_date"] = block or None
    out["uploaded_at"] = uploaded or None
    # Primary sort/filter date: block date when set, else upload day.
    out["date"] = block or uploaded

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
    elif file_path:
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
