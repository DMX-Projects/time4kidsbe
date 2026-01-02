from rest_framework import serializers

from accounts.serializers import UserSerializer
from .models import Event, EventMedia
from common.fields import RelativeFileField


class EventMediaSerializer(serializers.ModelSerializer):
    file = RelativeFileField()
    uploaded_by = UserSerializer(read_only=True)

    class Meta:
        model = EventMedia
        fields = ["id", "file", "media_type", "caption", "uploaded_by", "uploaded_at"]
        read_only_fields = ["id", "uploaded_by", "uploaded_at"]


class EventSerializer(serializers.ModelSerializer):
    media = EventMediaSerializer(many=True, read_only=True)
    franchise_city = serializers.CharField(source="franchise.city", read_only=True)
    franchise_name = serializers.CharField(source="franchise.name", read_only=True)
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
        read_only_fields = ["id", "created_at", "updated_at", "media", "franchise_name", "franchise_city", "year"]

    def get_year(self, obj: Event):
        if obj.start_date:
            return obj.start_date.year
        return None
