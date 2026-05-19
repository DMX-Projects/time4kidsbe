from rest_framework import serializers
from .models import HeroSlide, Holiday, HomeTestimonial, MarketingAsset, StudentsKitPage
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
            "category",
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


class MarketingAssetSerializer(serializers.ModelSerializer):
    file = RelativeFileField(required=False, allow_null=True)
    link = serializers.CharField(required=False, allow_blank=True, max_length=500)

    class Meta:
        model = MarketingAsset
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "slug": {"required": False},
            "title": {"required": False},
            "is_active": {"required": False},
        }

    def validate_link(self, value):
        value = (value or "").strip()
        if not value:
            return ""
        if not value.startswith(("http://", "https://")):
            raise serializers.ValidationError("Enter a valid URL starting with http:// or https://")
        return value

    def validate(self, attrs):
        if self.instance is None and not (attrs.get("slug") or "").strip():
            raise serializers.ValidationError({"slug": "This field is required."})
        return attrs

    def _apply_file_upload(self, instance, validated_data):
        new_file = validated_data.get("file")
        if not new_file:
            return validated_data
        validated_data["link"] = ""
        if instance and instance.file:
            try:
                instance.file.delete(save=False)
            except OSError:
                pass
        return validated_data

    def create(self, validated_data):
        validated_data = self._apply_file_upload(None, validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = self._apply_file_upload(instance, validated_data)
        return super().update(instance, validated_data)


class StudentsKitPageSerializer(serializers.ModelSerializer):
    image = RelativeImageField(required=False, allow_null=True)
    pdf = RelativeFileField(required=False, allow_null=True)

    def update(self, instance, validated_data):
        request = self.context.get("request")
        if request is not None:
            if str(request.data.get("clear_pdf", "")).lower() in ("1", "true", "yes"):
                if instance.pdf:
                    instance.pdf.delete(save=False)
                validated_data["pdf"] = None
            if str(request.data.get("clear_image", "")).lower() in ("1", "true", "yes"):
                if instance.image:
                    instance.image.delete(save=False)
                validated_data["image"] = None
        return super().update(instance, validated_data)

    class Meta:
        model = StudentsKitPage
        fields = [
            "id",
            "slug",
            "title",
            "short_label",
            "public_path",
            "image_alt",
            "link_label",
            "row_key",
            "academic_year",
            "image",
            "pdf",
            "order",
            "is_active",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "public_path", "row_key", "updated_at"]
