"""File-type rules for parent-app document categories (display + API filtering)."""

from __future__ import annotations

from pathlib import Path

from .models import DocumentCategory, ParentDocument

VIDEO_EXTENSIONS = {
    ".mp4",
    ".webm",
    ".mov",
    ".m4v",
    ".avi",
    ".mkv",
    ".mpeg",
    ".mpg",
    ".3gp",
    ".flv",
    ".wmv",
}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac", ".wma"}
PDF_ONLY_CATEGORIES = {
    DocumentCategory.PRESCHOOL_POLICIES,
    DocumentCategory.HOLIDAY_LISTS,
    DocumentCategory.STUDENT_TRANSFER_POLICY,
    DocumentCategory.CONTACT_US,
    DocumentCategory.GENERAL_RHYMES,
    DocumentCategory.PARENTING_TIPS,
}
MIXED_MEDIA_CATEGORIES = {DocumentCategory.VIDEOS}
AUDIO_ONLY_CATEGORIES = {
    DocumentCategory.AUDIO_RHYMES,
}


def _extension(file_name: str) -> str:
    return Path((file_name or "").split("?")[0]).suffix.lower()


def _is_video_url(path: str) -> bool:
    lower = (path or "").lower()
    return any(
        token in lower
        for token in (
            "youtube.com",
            "youtu.be",
            "mediadelivery.net",
            "vimeo.com",
            "/shorts/",
            "/embed/",
        )
    )


def parent_document_media_kind(file_name: str) -> str:
    path = (file_name or "").strip()
    if not path:
        return "unknown"
    if _is_video_url(path):
        return "video"
    ext = _extension(path)
    if ext == ".pdf":
        return "pdf"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in AUDIO_EXTENSIONS:
        return "audio"
    if ext:
        return "document"
    return "unknown"


def _parent_document_has_stored_file(field) -> bool:
    name = getattr(field, "name", "") or ""
    if not name.strip():
        return False
    try:
        return field.storage.exists(name)
    except Exception:
        return True


def parent_document_has_newsletter_video_embed(doc: ParentDocument) -> bool:
    return bool((doc.video_embed_url or "").strip())


def parent_document_has_newsletter_audio(doc: ParentDocument) -> bool:
    return _parent_document_has_stored_file(doc.audio_file)


def parent_document_has_listable_file(doc: ParentDocument) -> bool:
    name = getattr(doc.file, "name", "") or ""
    if not name.strip():
        return False
    try:
        if doc.file.storage.exists(name):
            return True
    except Exception:
        return True
    return False


def parent_document_matches_category_media(doc: ParentDocument) -> bool:
    """True if this row should appear in parent app for its category."""
    category = doc.category

    if category == DocumentCategory.HOLIDAY_LISTS:
        if parent_document_has_listable_file(doc) and parent_document_media_kind(doc.file.name) == "pdf":
            return True
        entries = doc.holiday_entries or []
        return bool(entries)

    if category == DocumentCategory.CLASS_TIMETABLE:
        if parent_document_has_newsletter_video_embed(doc) or parent_document_has_newsletter_audio(doc):
            return True
        if not parent_document_has_listable_file(doc):
            return False
        kind = parent_document_media_kind(doc.file.name)
        return kind not in ("video", "audio")

    if not parent_document_has_listable_file(doc):
        return False

    kind = parent_document_media_kind(doc.file.name)
    if category in PDF_ONLY_CATEGORIES:
        return kind == "pdf"
    if category in MIXED_MEDIA_CATEGORIES:
        return True
    if category in AUDIO_ONLY_CATEGORIES:
        return kind in ("audio", "video")
    return kind not in ("video", "audio")


def filter_parent_documents_by_media_type(queryset):
    ids = [doc.pk for doc in queryset if parent_document_matches_category_media(doc)]
    if not ids:
        return queryset.none()
    return queryset.filter(pk__in=ids)
