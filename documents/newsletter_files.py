from pathlib import Path

NEWSLETTER_EXTENSIONS = {".pdf", ".doc", ".docx"}
NEWSLETTER_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def is_newsletter_upload_file(file_obj) -> bool:
    name = (getattr(file_obj, "name", "") or "").lower()
    if Path(name).suffix in NEWSLETTER_EXTENSIONS:
        return True
    content_type = (getattr(file_obj, "content_type", "") or "").lower()
    return content_type in NEWSLETTER_CONTENT_TYPES


def is_pdf_upload_file(file_obj) -> bool:
    name = (getattr(file_obj, "name", "") or "").lower()
    if Path(name).suffix == ".pdf":
        return True
    content_type = (getattr(file_obj, "content_type", "") or "").lower()
    return content_type == "application/pdf"


VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv", ".mpeg", ".mpg", ".3gp"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".aac", ".flac", ".wma"}


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
