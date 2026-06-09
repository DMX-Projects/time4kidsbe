import json
from pathlib import Path

from django.db import IntegrityError
from rest_framework import serializers
from .holiday_entries import merge_holiday_entries, normalize_holiday_entries
from .models import ParentDocument, FranchiseDocument, FranchiseDocumentCategory, DocumentCategory, IndentRequest
from .state_utils import (
    DEFAULT_HOLIDAY_ACADEMIC_YEAR,
    effective_holiday_academic_year,
    effective_holiday_state,
    franchise_state_code,
)
from .newsletter_files import (
    is_audio_upload_file,
    is_newsletter_upload_file,
    is_pdf_upload_file,
)
from common.fields import RelativeFileField, RelativeImageField


class FlexibleHolidayEntriesField(serializers.JSONField):
    def to_internal_value(self, data):
        if isinstance(data, str):
            text = data.strip()
            if not text:
                return []
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError("Invalid holiday list data.") from exc
        return super().to_internal_value(data)


class ParentDocumentSerializer(serializers.ModelSerializer):
    file = RelativeFileField(required=False, allow_null=True)
    holiday_entries = serializers.SerializerMethodField()
    thumbnail = RelativeImageField(required=False, allow_null=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    franchise_name = serializers.CharField(source='franchise.name', read_only=True, allow_null=True)
    state_display = serializers.CharField(source='get_state_display', read_only=True, allow_null=True)
    display_title = serializers.SerializerMethodField()

    class Meta:
        model = ParentDocument
        fields = [
            'id', 'category', 'category_display', 'title', 'description',
            'file', 'thumbnail', 'franchise', 'franchise_name', 'is_active',
            'order', 'state', 'state_display', 'academic_year', 'holiday_entries',
            'period_start', 'period_end', 'display_title',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'franchise', 'is_active', 'created_at', 'updated_at']

    def get_holiday_entries(self, obj: ParentDocument) -> list:
        entries = obj.holiday_entries or []
        if obj.category != DocumentCategory.HOLIDAY_LISTS:
            return entries
        if not obj.franchise_id:
            return entries
        if not self.context.get("merge_holiday_for_parent"):
            return entries
        global_doc = (
            ParentDocument.objects.filter(
                is_active=True,
                category=DocumentCategory.HOLIDAY_LISTS,
                franchise__isnull=True,
                state=obj.state,
                academic_year=obj.academic_year,
            )
            .order_by("-updated_at")
            .first()
        )
        return merge_holiday_entries(
            global_doc.holiday_entries if global_doc else [],
            entries,
        )

    def _file_available(self, obj: ParentDocument) -> bool:
        if not obj.file:
            return False
        name = getattr(obj.file, "name", "") or ""
        if not name.strip():
            return False
        try:
            return obj.file.storage.exists(name)
        except Exception:
            return True

    def get_display_title(self, obj):
        """Return formatted title - for holiday lists, include state and academic year"""
        if obj.category == 'HOLIDAY_LISTS':
            year = effective_holiday_academic_year(obj)
            if obj.title:
                return f"{obj.title} ({year})"
            state_code = effective_holiday_state(obj)
            state_display = dict(ParentDocument.State.choices).get(state_code or "", "") if state_code else ""
            return f"{state_display} ({year})" if state_display else obj.title
        return obj.title

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self._file_available(instance):
            data["file"] = ""
        if instance.category == DocumentCategory.HOLIDAY_LISTS:
            state_code = effective_holiday_state(instance)
            if state_code and not data.get("state"):
                data["state"] = state_code
                data["state_display"] = dict(ParentDocument.State.choices).get(state_code, state_code)
            year = effective_holiday_academic_year(instance)
            if not (data.get("academic_year") or "").strip():
                data["academic_year"] = year
        # Remove franchise/franchise_name when null — no meaning to the parent
        if data.get("franchise") is None:
            data.pop("franchise", None)
            data.pop("franchise_name", None)
        return data


class FranchiseParentDocumentWriteSerializer(serializers.ModelSerializer):
    """Franchise centre: upload Newsletter and centre-specific holiday PDFs for their parents."""

    file = RelativeFileField(required=False, allow_null=True)
    category = serializers.ChoiceField(
        choices=[DocumentCategory.CLASS_TIMETABLE, DocumentCategory.HOLIDAY_LISTS],
        required=False,
        default=DocumentCategory.CLASS_TIMETABLE,
    )

    class Meta:
        model = ParentDocument
        fields = [
            "id",
            "category",
            "title",
            "description",
            "file",
            "state",
            "academic_year",
            "holiday_entries",
            "period_start",
            "period_end",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
    holiday_entries = FlexibleHolidayEntriesField(required=False)

    def _incoming_file(self):
        request = self.context.get("request")
        if not request:
            return None
        return getattr(request, "FILES", None).get("file")

    def _resolved_category(self, attrs):
        if attrs.get("category"):
            return attrs["category"]
        if self.instance is not None:
            return self.instance.category
        return DocumentCategory.CLASS_TIMETABLE

    def _resolved_holiday_entries(self, attrs):
        if "holiday_entries" in attrs:
            return normalize_holiday_entries(attrs["holiday_entries"])
        if self.instance is not None:
            return normalize_holiday_entries(self.instance.holiday_entries or [])
        return []

    def validate(self, attrs):
        uploaded = self._incoming_file()
        file_obj = attrs.get("file") or uploaded
        category = self._resolved_category(attrs)
        holiday_entries = self._resolved_holiday_entries(attrs)
        if "holiday_entries" in attrs or category == DocumentCategory.HOLIDAY_LISTS:
            attrs["holiday_entries"] = holiday_entries

        if category == DocumentCategory.HOLIDAY_LISTS:
            state = attrs.get("state") or (self.instance.state if self.instance else None)
            if not state:
                raise serializers.ValidationError({"state": "State is required for holiday lists."})
            if file_obj is not None:
                raise serializers.ValidationError({"file": "Holiday lists use manual entries only."})
            if self.instance is None and len(holiday_entries) == 0:
                raise serializers.ValidationError(
                    {"holiday_entries": "Add at least one holiday for your centre, or update an existing date."}
                )
            title = (attrs.get("title") or "").strip()
            if self.instance is None and not title:
                attrs["title"] = "Holiday list"
            if self.instance is None and not attrs.get("academic_year"):
                attrs["academic_year"] = "AY 2026-27"
            if self.instance is not None:
                attrs.pop("state", None)
        elif self.instance is None and not file_obj:
            raise serializers.ValidationError({"file": "Choose a file to upload."})
        elif category == DocumentCategory.CLASS_TIMETABLE:
            if file_obj is not None and not is_newsletter_upload_file(file_obj):
                raise serializers.ValidationError({"file": "Newsletter must be a PDF or Word document."})
            title = (attrs.get("title") or "").strip()
            if self.instance is None and not title and file_obj is not None:
                attrs["title"] = Path(getattr(file_obj, "name", "")).stem or "Newsletter"
            period_start = attrs.get("period_start")
            period_end = attrs.get("period_end")
            if self.instance is not None:
                if period_start is None:
                    period_start = self.instance.period_start
                if period_end is None:
                    period_end = self.instance.period_end
            if period_start and period_end and period_end < period_start:
                raise serializers.ValidationError({"period_end": "End date must be on or after start date."})
        else:
            raise serializers.ValidationError({"category": "Invalid document category for centre upload."})

        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        from accounts.profile_access import franchise_profile_for_user

        franchise = franchise_profile_for_user(request.user) if request else None
        if franchise is None:
            raise serializers.ValidationError({"detail": "Franchise profile not found."})
        uploaded = self._incoming_file()
        if uploaded and not validated_data.get("file"):
            validated_data["file"] = uploaded
        category = validated_data.pop("category", DocumentCategory.CLASS_TIMETABLE)
        validated_data["franchise"] = franchise
        validated_data["category"] = category
        validated_data["is_active"] = True
        return super().create(validated_data)

    def update(self, instance, validated_data):
        uploaded = self._incoming_file()
        if uploaded and not validated_data.get("file"):
            validated_data["file"] = uploaded
        validated_data.pop("category", None)
        return super().update(instance, validated_data)


class AdminParentDocumentSerializer(ParentDocumentSerializer):
    """Head office: CRUD parent app documents (global or per-centre)."""

    file = RelativeFileField(required=False, allow_null=True)
    thumbnail = RelativeImageField(required=False, allow_null=True)
    holiday_entries = FlexibleHolidayEntriesField(required=False)

    class Meta(ParentDocumentSerializer.Meta):
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _resolved_holiday_entries(self, attrs):
        if "holiday_entries" in attrs:
            return normalize_holiday_entries(attrs["holiday_entries"])
        if self.instance is not None:
            return normalize_holiday_entries(self.instance.holiday_entries or [])
        return []

    def validate(self, attrs):
        request = self.context.get("request")
        uploaded = getattr(request, "FILES", None).get("file") if request else None
        has_upload = bool(attrs.get("file") or uploaded)
        category = attrs.get("category") or (self.instance.category if self.instance else None)
        state = attrs.get("state")
        franchise = attrs.get("franchise")
        if franchise is None and self.instance is not None:
            franchise = self.instance.franchise
        if category == "HOLIDAY_LISTS":
            if not state and not (self.instance and self.instance.state):
                inferred = franchise_state_code(franchise) if franchise else None
                if inferred:
                    attrs["state"] = inferred
                    state = inferred
            if not state and not (self.instance and self.instance.state):
                raise serializers.ValidationError({"state": "State is required for holiday lists."})
            if not (attrs.get("academic_year") or "").strip():
                if self.instance and (self.instance.academic_year or "").strip():
                    attrs["academic_year"] = self.instance.academic_year
                else:
                    attrs["academic_year"] = DEFAULT_HOLIDAY_ACADEMIC_YEAR
        file_obj = attrs.get("file") or uploaded
        if file_obj is not None:
            if category == DocumentCategory.PRESCHOOL_POLICIES and not is_pdf_upload_file(file_obj):
                raise serializers.ValidationError({"file": "Preschool policies must be a PDF file."})
            if category == DocumentCategory.AUDIO_RHYMES and not is_audio_upload_file(file_obj):
                raise serializers.ValidationError({"file": "Audio Rhymes accepts audio files only."})
        if category == "CLASS_TIMETABLE" and file_obj is not None and not is_newsletter_upload_file(file_obj):
            raise serializers.ValidationError({"file": "Newsletter must be a PDF or Word document."})
        if category == "HOLIDAY_LISTS":
            holiday_entries = self._resolved_holiday_entries(attrs)
            attrs["holiday_entries"] = holiday_entries
            if file_obj is not None and not is_pdf_upload_file(file_obj):
                raise serializers.ValidationError({"file": "Holiday lists must be a PDF file."})
            has_existing_file = bool(self.instance and self.instance.file)
            if (
                self.instance is None
                and not has_upload
                and len(holiday_entries) == 0
            ):
                raise serializers.ValidationError(
                    {"file": "Upload a PDF or add at least one holiday with a date."}
                )
            if (
                self.instance is not None
                and not has_upload
                and not has_existing_file
                and len(holiday_entries) == 0
            ):
                raise serializers.ValidationError(
                    {"file": "Upload a PDF or add at least one holiday with a date."}
                )
        elif self.instance is None and not has_upload:
            raise serializers.ValidationError({"file": "Choose a file to upload."})
        return attrs


class FranchiseCentreDocumentCreateSerializer(serializers.ModelSerializer):
    """Franchise centre: upload files to their own resource hub (not global HO rows)."""

    file = RelativeFileField()
    category_display = serializers.CharField(source="get_category_display", read_only=True)
    franchise_name = serializers.CharField(source="franchise.name", read_only=True, allow_null=True)
    display_title = serializers.SerializerMethodField()

    class Meta:
        model = FranchiseDocument
        fields = [
            "id",
            "category",
            "category_display",
            "title",
            "description",
            "file",
            "display_title",
            "franchise_name",
            "academic_year",
            "is_active",
            "order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "category_display",
            "display_title",
            "franchise_name",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def get_display_title(self, obj: FranchiseDocument) -> str:
        if obj.academic_year:
            return f"{obj.title} ({obj.academic_year})"
        return obj.title

    def validate_category(self, value: str) -> str:
        valid = {c[0] for c in FranchiseDocumentCategory.choices}
        if value not in valid:
            raise serializers.ValidationError("Invalid category.")
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        uploaded = getattr(request, "FILES", None).get("file") if request else None
        if not attrs.get("file") and not uploaded:
            raise serializers.ValidationError({"file": "Choose a file to upload."})
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        uploaded = getattr(request, "FILES", None).get("file") if request else None
        if uploaded and not validated_data.get("file"):
            validated_data["file"] = uploaded
        file_obj = validated_data.get("file")
        if file_obj is not None:
            name = getattr(file_obj, "name", "") or ""
            if name and not (validated_data.get("source_path") or "").strip():
                validated_data["source_path"] = Path(name).name
        return super().create(validated_data)


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

    def validate_category(self, value: str) -> str:
        valid = {c[0] for c in FranchiseDocumentCategory.choices}
        if value not in valid:
            raise serializers.ValidationError("Invalid category.")
        return value

    def validate_embed_url(self, value: str | None) -> str:
        return (value or "").strip()

    def validate_source_path(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if len(cleaned) > 512:
            raise serializers.ValidationError("Checklist path is too long (max 512 characters).")
        return cleaned

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
            existing = FranchiseDocument.objects.filter(source_path=source_path).first()
            if existing:
                return self.update(existing, validated_data)
        try:
            return super().create(validated_data)
        except IntegrityError as exc:
            if "source_path" in str(exc).lower():
                raise serializers.ValidationError(
                    {
                        "source_path": (
                            "Another document already uses this checklist path. "
                            "Delete the old upload or use Edit on that row."
                        )
                    }
                ) from exc
            raise

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

