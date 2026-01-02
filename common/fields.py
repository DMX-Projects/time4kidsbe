from rest_framework import serializers

class RelativeImageField(serializers.ImageField):
    def to_representation(self, value):
        if not value:
            return None
        url = super().to_representation(value)
        # If the URL is absolute (contains http/https), strip the domain
        if url and "http" in url:
            from django.conf import settings
            # We can't easily guess the exact domain DRF used, but we know it usually prepends it.
            # A safer way relies on the fact that value.url serves the relative path if configured correctly,
            # but DRF's ImageField wraps it.
            # However, simpler approach: return value.url directly if available.
            try:
                return value.url
            except AttributeError:
                pass
        return url

class RelativeFileField(serializers.FileField):
    def to_representation(self, value):
        if not value:
            return None
        url = super().to_representation(value)
        if url and "http" in url:
            try:
                return value.url
            except AttributeError:
                pass
        return url
