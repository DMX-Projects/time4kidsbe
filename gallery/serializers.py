from rest_framework import serializers

from common.fields import RelativeFileField, RelativeImageField
from .models import GallerySection, MediaItem


class GallerySectionSerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = GallerySection
        fields = [
            "id",
            "title",
            "slug",
            "order",
            "is_active",
            "item_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at", "item_count"]

    def get_item_count(self, obj: GallerySection) -> int:
        return obj.items.count()


class MediaItemSerializer(serializers.ModelSerializer):
    file = RelativeFileField(required=False, allow_null=True)
    section_title = serializers.CharField(source="section.title", read_only=True, allow_null=True)

    class Meta:
        model = MediaItem
        fields = [
            "id",
            "section",
            "section_title",
            "title",
            "caption",
            "author",
            "location",
            "file",
            "embed_url",
            "media_type",
            "category",
            "order",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "section_title"]

    def validate(self, attrs):
        request = self.context.get("request")
        uploaded = getattr(request, "FILES", None).get("file") if request else None
        file_val = attrs.get("file") or uploaded
        embed = (attrs.get("embed_url") or "").strip()
        if self.instance:
            has_file = bool(file_val or self.instance.file)
            has_embed = bool(embed or (self.instance.embed_url or "").strip())
        else:
            has_file = bool(file_val)
            has_embed = bool(embed)
        if not has_file and not has_embed:
            raise serializers.ValidationError(
                {"detail": "Upload a file or provide an embed / iframe video URL."}
            )
        media_type = attrs.get("media_type") or (self.instance.media_type if self.instance else "image")
        if has_embed and not has_file:
            attrs["media_type"] = "embed"
        elif media_type == "embed" and has_file:
            attrs["media_type"] = "video" if (file_val or "").lower().endswith((".mp4", ".webm", ".mov")) else "image"
        return attrs
