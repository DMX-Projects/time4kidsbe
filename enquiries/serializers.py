from rest_framework import serializers

from franchises.models import Franchise
from .models import Enquiry, EnquiryType


class EnquirySerializer(serializers.ModelSerializer):
    franchise_slug = serializers.CharField(write_only=True, required=False, allow_blank=True)
    franchise_name = serializers.CharField(read_only=True, source="franchise.name")

    class Meta:
        model = Enquiry
        fields = [
            "id",
            "enquiry_type",
            "name",
            "email",
            "phone",
            "message",
            "city",
            "child_age",
            "franchise",
            "franchise_slug",
            "franchise_name",
            "created_at",
        ]
        read_only_fields = ["id", "franchise", "created_at"]

    def validate(self, attrs):
        enquiry_type = attrs.get("enquiry_type")
        franchise_slug = attrs.get("franchise_slug")
        if enquiry_type == EnquiryType.ADMISSION and not franchise_slug:
            raise serializers.ValidationError("franchise_slug is required for admission enquiries")
        return attrs

    def create(self, validated_data):
        franchise_slug = validated_data.pop("franchise_slug", None)
        franchise = None
        if franchise_slug:
            franchise = Franchise.objects.filter(slug=franchise_slug).first()
        validated_data["franchise"] = franchise
        return Enquiry.objects.create(**validated_data)
