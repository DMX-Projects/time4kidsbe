from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from accounts.serializers import UserSerializer
from .models import Event, EventMedia
from common.fields import RelativeFileField

MAX_EVENT_GALLERY_IMAGE_BYTES = 1 * 1024 * 1024


class EventMediaSerializer(serializers.ModelSerializer):
    file = RelativeFileField()
    uploaded_by = UserSerializer(read_only=True)

    class Meta:
        model = EventMedia
        fields = ["id", "file", "media_type", "caption", "uploaded_by", "uploaded_at"]
        read_only_fields = ["id", "uploaded_by", "uploaded_at"]

    def validate(self, attrs):
        uploaded = attrs.get("file")
        media_type = attrs.get("media_type") or getattr(self.instance, "media_type", None)
        if (
            uploaded
            and media_type == EventMedia.MediaType.IMAGE
            and uploaded.size > MAX_EVENT_GALLERY_IMAGE_BYTES
        ):
            mb = uploaded.size / (1024 * 1024)
            raise serializers.ValidationError(
                {"file": f"Each image must be 1 MB or smaller (this file is {mb:.2f} MB)."}
            )
        return attrs


class EventSerializer(serializers.ModelSerializer):
    media = EventMediaSerializer(many=True, read_only=True)
    franchise = serializers.SerializerMethodField()
    franchise_city = serializers.SerializerMethodField()
    franchise_name = serializers.SerializerMethodField()
    year = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id",
            "franchise",
            "franchise_name",
            "franchise_city",
            "title",
            "description",
            "start_date",
            "end_date",
            "location",
            "year",
            "created_at",
            "updated_at",
            "media",
        ]
        read_only_fields = ["id", "franchise", "created_at", "updated_at", "media", "franchise_name", "franchise_city", "year"]

    def get_year(self, obj: Event):
        if obj.start_date:
            return obj.start_date.year
        return None

    def _safe_franchise(self, obj: Event):
        if not obj.franchise_id:
            return None
        try:
            return obj.franchise
        except ObjectDoesNotExist:
            return None

    def get_franchise(self, obj: Event):
        fr = self._safe_franchise(obj)
        return getattr(fr, "id", None)

    def get_franchise_name(self, obj: Event):
        fr = self._safe_franchise(obj)
        return getattr(fr, "name", None) if fr is not None else None

    def get_franchise_city(self, obj: Event):
        fr = self._safe_franchise(obj)
        return getattr(fr, "city", None) if fr is not None else None
