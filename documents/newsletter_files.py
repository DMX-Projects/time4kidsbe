from pathlib import Path

NEWSLETTER_EXTENSIONS = {".pdf", ".doc", ".docx"}
NEWSLETTER_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _file_head(file_obj, n: int = 8) -> bytes:
    read = getattr(file_obj, "read", None)
    if not read:
        return b""
    pos = file_obj.tell() if hasattr(file_obj, "tell") else None
    try:
        chunk = read(n)
        return chunk if isinstance(chunk, bytes) else b""
    except Exception:
        return b""
    finally:
        if pos is not None and hasattr(file_obj, "seek"):
            try:
                file_obj.seek(pos)
            except Exception:
                pass


def is_newsletter_upload_file(file_obj) -> bool:
    name = (getattr(file_obj, "name", "") or "").lower()
    ext = Path(name).suffix
    if ext in NEWSLETTER_EXTENSIONS:
        return True
    content_type = (getattr(file_obj, "content_type", "") or "").lower()
    if content_type in NEWSLETTER_CONTENT_TYPES:
        return True
    # Some browsers/OS exports use application/octet-stream with no extension.
    head = _file_head(file_obj)
    if head.startswith(b"%PDF"):
        return True
    if ext == ".docx" and head.startswith(b"PK"):
        return True
    if ext == ".doc" and head.startswith(b"\xd0\xcf\x11\xe0"):
        return True
    return False


def is_pdf_upload_file(file_obj) -> bool:
    name = (getattr(file_obj, "name", "") or "").lower()
    if Path(name).suffix == ".pdf":
        return True
    content_type = (getattr(file_obj, "content_type", "") or "").lower()
    return content_type == "application/pdf"


VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv", ".mpeg", ".mpg", ".3gp"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac", ".wma"}

# Newsletter audio — phones often export .mp4 / .m4a / .amr with video/* or octet-stream MIME.
NEWSLETTER_AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".ogg",
    ".aac",
    ".flac",
    ".wma",
    ".mp4",
    ".amr",
    ".opus",
    ".caf",
    ".aiff",
    ".aif",
    ".mpeg",
    ".mpg",
    ".3gp",
    ".weba",
    ".webm",
}

NEWSLETTER_AUDIO_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/ogg",
    "audio/aac",
    "audio/flac",
    "audio/x-ms-wma",
    "audio/amr",
    "audio/opus",
    "audio/webm",
    "audio/aiff",
    "audio/x-caf",
    "video/mp4",
    "application/octet-stream",
}


def is_video_upload_file(file_obj) -> bool:
    name = (getattr(file_obj, "name", "") or "").lower()
    if Path(name).suffix in VIDEO_EXTENSIONS:
        return True
    content_type = (getattr(file_obj, "content_type", "") or "").lower()
    return content_type.startswith("video/")


def is_audio_upload_file(file_obj) -> bool:
    name = (getattr(file_obj, "name", "") or "").lower()
    if Path(name).suffix in AUDIO_EXTENSIONS:
        return True
    content_type = (getattr(file_obj, "content_type", "") or "").lower()
    return content_type.startswith("audio/")


def is_audio_rhymes_upload_file(file_obj) -> bool:
    """Audio Rhymes — standard audio plus MP4 (rhyme files are often saved as .mp4)."""
    if is_audio_upload_file(file_obj):
        return True
    name = (getattr(file_obj, "name", "") or "").lower()
    if Path(name).suffix == ".mp4":
        return True
    content_type = (getattr(file_obj, "content_type", "") or "").lower()
    return content_type == "video/mp4"


def is_newsletter_audio_upload_file(file_obj) -> bool:
    """Permissive audio check for newsletter uploads (MP4/M4A/AMR media from phones)."""
    name = (getattr(file_obj, "name", "") or "").lower()
    ext = Path(name).suffix
    if ext in NEWSLETTER_AUDIO_EXTENSIONS:
        return True
    content_type = (getattr(file_obj, "content_type", "") or "").lower()
    if content_type.startswith("audio/"):
        return True
    if content_type in NEWSLETTER_AUDIO_CONTENT_TYPES and ext in NEWSLETTER_AUDIO_EXTENSIONS | {""}:
        return True
    return False
