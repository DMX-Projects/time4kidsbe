from rest_framework import serializers
from .models import Update, SocialMediaUpload
from common.fields import RelativeFileField

class UpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Update
        fields = ['id', 'franchise', 'text', 'start_date', 'end_date', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['franchise']


class SocialMediaUploadSerializer(serializers.ModelSerializer):
    file = RelativeFileField()
    franchise_name = serializers.CharField(source="franchise.name", read_only=True, allow_null=True)

    class Meta:
        model = SocialMediaUpload
        fields = [
            "id",
            "franchise",
            "franchise_name",
            "media_type",
            "title",
            "caption",
            "file",
            "status",
            "admin_notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "franchise", "created_at", "updated_at"]
