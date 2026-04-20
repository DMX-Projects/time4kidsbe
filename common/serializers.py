from rest_framework import serializers
from .models import HeroSlide, Holiday, HomeTestimonial
from .fields import RelativeImageField, RelativeFileField

class HeroSlideSerializer(serializers.ModelSerializer):
    image = RelativeImageField()
    mobile_image = RelativeImageField(required=False, allow_null=True)

    class Meta:
        model = HeroSlide
        fields = '__all__'


class HomeTestimonialSerializer(serializers.ModelSerializer):
    class Meta:
        model = HomeTestimonial
        fields = [
            "id",
            "text",
            "author",
            "relation",
            "location",
            "rating",
            "order",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for key in ("text", "author", "relation", "location"):
            val = data.get(key)
            if val is None:
                data[key] = ""
            elif not isinstance(val, str):
                data[key] = str(val)
        try:
            r = int(data.get("rating", 5))
        except (TypeError, ValueError):
            r = 5
        data["rating"] = max(1, min(5, r))
        return data


class HolidaySerializer(serializers.ModelSerializer):
    document = RelativeFileField()
    state_display = serializers.CharField(source='get_state_display', read_only=True)
    display_title = serializers.SerializerMethodField()

    class Meta:
        model = Holiday
        fields = ['id', 'state', 'state_display', 'academic_year', 'document', 'title', 'display_title', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_display_title(self, obj):
        """Return title if provided, otherwise state name"""
        return obj.title or obj.get_state_display()
