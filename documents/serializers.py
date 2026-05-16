from pathlib import Path

from rest_framework import serializers
from .models import ParentDocument, FranchiseDocument, FranchiseDocumentCategory, IndentRequest
from common.fields import RelativeFileField, RelativeImageField


class ParentDocumentSerializer(serializers.ModelSerializer):
    file = RelativeFileField()
    thumbnail = RelativeImageField(required=False, allow_null=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    franchise_name = serializers.CharField(source='franchise.name', read_only=True, allow_null=True)
    state_display = serializers.CharField(source='get_state_display', read_only=True, allow_null=True)
    display_title = serializers.SerializerMethodField()

    class Meta:
        model = ParentDocument
        fields = ['id', 'category', 'category_display', 'title', 'description', 
                  'file', 'thumbnail', 'franchise', 'franchise_name', 'is_active', 
                  'order', 'state', 'state_display', 'academic_year', 'display_title',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'franchise', 'is_active', 'created_at', 'updated_at']

    def get_display_title(self, obj):
        """Return formatted title - for holiday lists, include state and academic year"""
        if obj.category == 'HOLIDAY_LISTS':
            if obj.title:
                return f"{obj.title} ({obj.academic_year})" if obj.academic_year else obj.title
            state_display = obj.get_state_display() if obj.state else ''
            year = f" ({obj.academic_year})" if obj.academic_year else ''
            return f"{state_display}{year}" if state_display else obj.title
        return obj.title


class FranchiseDocumentSerializer(serializers.ModelSerializer):
    file = RelativeFileField()
    franchise_name = serializers.CharField(source="franchise.name", read_only=True, allow_null=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    display_title = serializers.SerializerMethodField()

    class Meta:
        model = FranchiseDocument
        fields = [
            "id",
            "category",
            "category_display",
            "title",
            "display_title",
            "description",
            "file",
            "embed_url",
            "source_path",
            "franchise",
            "franchise_name",
            "academic_year",
            "is_active",
            "order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_display_title(self, obj: FranchiseDocument) -> str:
        if obj.academic_year:
            return f"{obj.title} ({obj.academic_year})"
        return obj.title


class AdminFranchiseDocumentSerializer(serializers.ModelSerializer):
    """Admin CRUD: file optional on update; required on create."""

    file = RelativeFileField(required=False, allow_null=True)
    franchise_name = serializers.CharField(source="franchise.name", read_only=True, allow_null=True)
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    display_title = serializers.SerializerMethodField()

    class Meta:
        model = FranchiseDocument
        fields = [
            "id",
            "category",
            "category_display",
            "title",
            "display_title",
            "description",
            "file",
            "embed_url",
            "source_path",
            "franchise",
            "franchise_name",
            "academic_year",
            "is_active",
            "order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_display_title(self, obj: FranchiseDocument) -> str:
        if obj.academic_year:
            return f"{obj.title} ({obj.academic_year})"
        return obj.title

    def validate(self, attrs):
        request = self.context.get("request")
        uploaded = getattr(request, "FILES", None).get("file") if request else None
        has_file = bool(attrs.get("file") or uploaded)
        has_embed = bool((attrs.get("embed_url") or "").strip())
        if self.instance is None:
            if not has_file and not has_embed:
                raise serializers.ValidationError(
                    {"detail": "Upload a file or provide an embed/video link."}
                )
        else:
            merged_file = has_file or bool(self.instance.file)
            merged_embed = has_embed or bool((self.instance.embed_url or "").strip())
            if not merged_file and not merged_embed:
                raise serializers.ValidationError(
                    {"detail": "Document must have a file or an embed link."}
                )
        return attrs

    def _incoming_uploaded_file(self):
        request = self.context.get("request")
        if not request:
            return None
        return getattr(request, "FILES", None).get("file")

    def _ensure_file_in_validated(self, validated_data: dict) -> None:
        if validated_data.get("file"):
            return
        uploaded = self._incoming_uploaded_file()
        if uploaded:
            validated_data["file"] = uploaded

    def _default_source_path(self, validated_data: dict, instance=None) -> str:
        explicit = (validated_data.get("source_path") or "").strip()
        if explicit:
            return explicit
        if instance and (instance.source_path or "").strip():
            return instance.source_path.strip()
        file_obj = validated_data.get("file") or self._incoming_uploaded_file()
        if file_obj is not None:
            name = getattr(file_obj, "name", "") or ""
            if name:
                return Path(name).name
        if instance and instance.file:
            return Path(instance.file.name).name
        return ""

    def create(self, validated_data):
        self._ensure_file_in_validated(validated_data)
        source_path = self._default_source_path(validated_data)
        if source_path:
            validated_data["source_path"] = source_path
        return super().create(validated_data)

    def update(self, instance, validated_data):
        self._ensure_file_in_validated(validated_data)
        merged = {
            "source_path": validated_data.get("source_path", instance.source_path),
            "file": validated_data.get("file", instance.file),
        }
        source_path = self._default_source_path({**validated_data, **merged}, instance=instance)
        if source_path and not (validated_data.get("source_path") or "").strip():
            validated_data["source_path"] = source_path
        return super().update(instance, validated_data)


class IndentRequestSerializer(serializers.ModelSerializer):
    franchise_name = serializers.CharField(source="franchise.name", read_only=True)

    class Meta:
        model = IndentRequest
        fields = [
            "id",
            "franchise",
            "franchise_name",
            "region",
            "academic_year",
            "notes",
            "status",
            "requested_at",
            "updated_at",
        ]
        read_only_fields = ["id", "franchise", "requested_at", "updated_at"]

