from rest_framework import serializers

def _relative_media_url(value) -> str | None:
    """Always return /media/... so the frontend picks the public domain (not request Host)."""
    if not value:
        return None
    try:
        url = value.url
    except (AttributeError, OSError, ValueError):
        return None
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.path or url
    return url


class RelativeImageField(serializers.ImageField):
    def to_representation(self, value):
        return _relative_media_url(value)


class RelativeFileField(serializers.FileField):
    def to_representation(self, value):
        return _relative_media_url(value)
