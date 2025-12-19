from rest_framework import serializers

from .models import Career


class CareerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Career
        fields = [
            "id",
            "title",
            "description",
            "location",
            "apply_email",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
