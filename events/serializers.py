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
    media = serializers.SerializerMethodField()
    video_links = serializers.SerializerMethodField()
    franchise = serializers.SerializerMethodField()
    franchise_city = serializers.SerializerMethodField()
    franchise_name = serializers.SerializerMethodField()
    year = serializers.SerializerMethodField()
    audience_label = serializers.SerializerMethodField()

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
            "class_name",
            "audience_label",
            "year",
            "created_at",
            "updated_at",
            "media",
            "video_links",
        ]
        read_only_fields = [
            "id",
            "franchise",
            "created_at",
            "updated_at",
            "media",
            "video_links",
            "franchise_name",
            "franchise_city",
            "year",
            "audience_label",
        ]

    def get_audience_label(self, obj: Event) -> str:
        target_class = (obj.class_name or "").strip()
        if target_class:
            return target_class
        return "All classes"

    def get_video_links(self, obj: Event):
        if self.context.get("omit_video_links"):
            return []
        from events.video_links import parse_event_video_links

        return parse_event_video_links(obj.description)

    def get_media(self, obj: Event):
        from events.video_links import video_link_media_rows

        uploaded = EventMediaSerializer(obj.media.all(), many=True).data
        return list(uploaded) + video_link_media_rows(obj.description)

    def to_representation(self, instance):
        from events.video_links import strip_event_video_links

        data = super().to_representation(instance)
        data["description"] = strip_event_video_links(instance.description)
        if not (data.get("class_name") or "").strip():
            data["class_name"] = "All classes"
        return data

    def validate_class_name(self, value):
        from students.portal_views import normalize_portal_class_name

        raw = (value or "").strip()
        if raw.lower() in ("all classes", "all"):
            return ""
        return normalize_portal_class_name(raw)

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
