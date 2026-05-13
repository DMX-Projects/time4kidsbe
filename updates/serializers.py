from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from common.fields import RelativeFileField
from franchises.models import Franchise

from .models import SocialMediaUpload, Update


class UpdateSerializer(serializers.ModelSerializer):
    franchise = serializers.SerializerMethodField()

    class Meta:
        model = Update
        fields = ['id', 'franchise', 'placement', 'text', 'start_date', 'end_date', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['franchise']

    def get_franchise(self, obj: Update):
        if not obj.franchise_id:
            return None
        try:
            _ = obj.franchise
            return obj.franchise_id
        except ObjectDoesNotExist:
            return None


class SocialMediaUploadSerializer(serializers.ModelSerializer):
    file = RelativeFileField()
    franchise = serializers.SerializerMethodField()
    franchise_name = serializers.SerializerMethodField()

    def get_franchise(self, obj: SocialMediaUpload):
        if not obj.franchise_id:
            return None
        try:
            _ = obj.franchise
            return obj.franchise_id
        except Franchise.DoesNotExist:
            return None

    def get_franchise_name(self, obj: SocialMediaUpload):
        if not obj.franchise_id:
            return None
        try:
            return obj.franchise.name
        except Franchise.DoesNotExist:
            return None

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
