from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from accounts.profile_access import franchise_profile_for_user, parent_profile_for_user
from franchises.models import ParentProfile

from .models import (
    Announcement,
    AnnouncementCampaign,
    AttendanceRecord,
    FeeRecord,
    Grade,
    HomeworkAssignment,
    ParentNotificationRead,
    StudentAchievement,
    StudentProfile,
    StudentTransportAssignment,
    SupportTicket,
    TransportRoute,
    TransportTrip,
    TransportTripLocation,
)
from common.fields import RelativeFileField, RelativeImageField


class GradeSerializer(serializers.ModelSerializer):
    percentage = serializers.ReadOnlyField()
    student = serializers.PrimaryKeyRelatedField(queryset=StudentProfile.objects.all())
    student_name = serializers.CharField(source="student.full_name", read_only=True)

    class Meta:
        model = Grade
        fields = [
            "id",
            "student",
            "student_name",
            "subject",
            "exam_type",
            "marks_obtained",
            "total_marks",
            "grade",
            "percentage",
            "exam_date",
            "remarks",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "student_name"]

    def validate_student(self, value):
        request = self.context.get("request")
        franchise = franchise_profile_for_user(getattr(request, "user", None))
        if not franchise or value.parent.franchise_id != franchise.id:
            raise serializers.ValidationError("Student is not enrolled at your centre.")
        return value


class StudentProfileSerializer(serializers.ModelSerializer):
    profile_picture = RelativeImageField(required=False, allow_null=True)
    full_name = serializers.ReadOnlyField()
    parent_info = serializers.SerializerMethodField(read_only=True)
    grades_count = serializers.SerializerMethodField(read_only=True)
    id_card_no = serializers.CharField(source="Idcardno", required=False, allow_blank=True)
    academic_year = serializers.CharField(source="Year", required=False, allow_blank=True)

    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "parent",
            "first_name",
            "last_name",
            "full_name",
            "class_name",
            "section",
            "gender",
            "roll_number",
            "id_card_no",
            "academic_year",
            "date_of_birth",
            "admission_date",
            "profile_picture",
            "is_active",
            "blood_group",
            "emergency_contact",
            "parent_info",
            "grades_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'parent_info', 'grades_count']

    def get_parent_info(self, obj):
        try:
            parent = obj.parent
        except ObjectDoesNotExist:
            return {"id": None, "parent_name": "", "franchise_name": ""}

        parent_id = getattr(parent, "pk", None)
        parent_name = ""
        try:
            user = parent.user
            parent_name = (
                (getattr(user, "full_name", None) or "").strip()
                or getattr(user, "email", "")
                or ""
            )
        except ObjectDoesNotExist:
            pass

        franchise_name = ""
        try:
            franchise_name = (parent.franchise.name or "").strip()
        except ObjectDoesNotExist:
            pass

        return {
            "id": parent_id,
            "parent_name": parent_name,
            "franchise_name": franchise_name,
        }

    def get_grades_count(self, obj):
        return obj.grades.count()


class StudentDetailSerializer(StudentProfileSerializer):
    """Extended serializer with grades"""
    grades = GradeSerializer(many=True, read_only=True)

    class Meta(StudentProfileSerializer.Meta):
        fields = StudentProfileSerializer.Meta.fields + ['grades']


class StudentMiniSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = StudentProfile
        fields = ["id", "full_name", "class_name", "roll_number", "gender"]


class FranchiseStudentSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    parent = serializers.PrimaryKeyRelatedField(queryset=ParentProfile.objects.all())
    id_card_no = serializers.CharField(source="Idcardno", required=False, allow_blank=True)
    academic_year = serializers.CharField(source="Year", required=False, allow_blank=True)

    class Meta:
        model = StudentProfile
        fields = [
            "id",
            "parent",
            "first_name",
            "last_name",
            "full_name",
            "class_name",
            "section",
            "gender",
            "roll_number",
            "id_card_no",
            "academic_year",
            "date_of_birth",
            "admission_date",
            "is_active",
            "blood_group",
            "emergency_contact",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "full_name"]

    def validate_parent(self, value):
        request = self.context.get("request")
        franchise = franchise_profile_for_user(getattr(request, "user", None))
        if not franchise or value.franchise_id != franchise.id:
            raise serializers.ValidationError("Parent is not assigned to your centre.")
        return value


class AdminStudentAchievementSerializer(serializers.ModelSerializer):
    """Head office publishes achievements for any centre."""

    student_name = serializers.SerializerMethodField()
    franchise_name = serializers.SerializerMethodField()

    class Meta:
        model = StudentAchievement
        fields = [
            "id",
            "franchise",
            "franchise_name",
            "student",
            "student_name",
            "title",
            "notes",
            "achieved_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "franchise_name", "student_name", "created_at", "updated_at"]

    def get_student_name(self, obj):
        if not obj.student_id:
            return None
        try:
            st = obj.student
        except ObjectDoesNotExist:
            return ""
        return getattr(st, "full_name", "") or ""

    def get_franchise_name(self, obj):
        try:
            return obj.franchise.name if obj.franchise_id else ""
        except ObjectDoesNotExist:
            return ""

    def validate_franchise(self, value):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_admin", False):
            raise serializers.ValidationError("Invalid franchise.")
        if value.admin_id != user.id:
            raise serializers.ValidationError("Franchise is not in your account.")
        return value

    def validate_student(self, value):
        if value is None:
            return value
        franchise = self.initial_data.get("franchise")
        if self.instance and not franchise:
            franchise = self.instance.franchise_id
        if franchise and value.parent.franchise_id != int(franchise):
            raise serializers.ValidationError("Student is not enrolled at the selected centre.")
        return value


class StudentAchievementSerializer(serializers.ModelSerializer):
    """Franchise achievements list; student is optional (centre-wide) and FK may be orphan on live DB."""

    student_name = serializers.SerializerMethodField()

    class Meta:
        model = StudentAchievement
        fields = [
            "id",
            "franchise",
            "student",
            "student_name",
            "title",
            "notes",
            "achieved_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "franchise", "created_at", "updated_at", "student_name"]

    def get_student_name(self, obj):
        if not obj.student_id:
            return None
        try:
            st = obj.student
        except ObjectDoesNotExist:
            return ""
        return getattr(st, "full_name", "") or ""

    def validate_student(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        franchise = franchise_profile_for_user(getattr(request, "user", None))
        if not franchise or value.parent.franchise_id != franchise.id:
            raise serializers.ValidationError("Student is not enrolled at your centre.")
        return value


class ParentStudentAchievementSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    scope = serializers.SerializerMethodField()

    class Meta:
        model = StudentAchievement
        fields = ["id", "title", "notes", "achieved_date", "student_name", "scope", "created_at"]

    def get_student_name(self, obj):
        if not obj.student_id:
            return None
        try:
            st = obj.student
        except ObjectDoesNotExist:
            return None
        return getattr(st, "full_name", "") or None

    def get_scope(self, obj):
        return "centre" if obj.student_id is None else "student"


class HomeworkAssignmentSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    is_read = serializers.SerializerMethodField()
    read_status = serializers.SerializerMethodField()
    read_count = serializers.SerializerMethodField()
    viewed_by_parents = serializers.SerializerMethodField()
    attachment = RelativeFileField(required=False, allow_null=True)

    class Meta:
        model = HomeworkAssignment
        fields = [
            "id",
            "franchise",
            "student",
            "student_name",
            "class_name",
            "assigned_date",
            "title",
            "description",
            "attachment",
            "attachment_name",
            "attachment_kind",
            "is_read",
            "read_status",
            "read_count",
            "viewed_by_parents",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "franchise",
            "created_at",
            "updated_at",
            "student_name",
            "is_read",
            "read_status",
            "read_count",
            "viewed_by_parents",
        ]

    def validate_attachment(self, value):
        if not value:
            return value
        max_size = 5 * 1024 * 1024  # 5MB
        if getattr(value, "size", 0) and value.size > max_size:
            raise serializers.ValidationError("Attachment too large. Max 5MB.")
        ct = (getattr(value, "content_type", "") or "").lower()
        name = (getattr(value, "name", "") or "").lower()
        is_pdf = ct == "application/pdf" or name.endswith(".pdf")
        is_image = ct.startswith("image/")
        if not (is_pdf or is_image):
            raise serializers.ValidationError("Only image or PDF attachments are allowed.")
        return value

    def validate_class_name(self, value):
        from students.portal_views import normalize_portal_class_name

        return normalize_portal_class_name(value or "")

    def validate(self, attrs):
        # Auto-fill attachment metadata when a new file is posted.
        attachment = attrs.get("attachment")
        if attachment:
            ct = (getattr(attachment, "content_type", "") or "").lower()
            name = (getattr(attachment, "name", "") or "").strip()
            if name and not attrs.get("attachment_name"):
                attrs["attachment_name"] = name
            if not attrs.get("attachment_kind"):
                attrs["attachment_kind"] = "PDF" if ct == "application/pdf" or name.lower().endswith(".pdf") else "IMAGE"
        # If attachment removed (set to null), clear metadata too.
        if "attachment" in attrs and not attrs.get("attachment"):
            attrs["attachment_name"] = ""
            attrs["attachment_kind"] = ""
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not (data.get("class_name") or "").strip():
            data["class_name"] = "All classes"
        return data

    def get_student_name(self, obj):
        if obj.student_id:
            try:
                st = obj.student
                return getattr(st, "full_name", "") or ""
            except ObjectDoesNotExist:
                return ""
        class_name = (getattr(obj, "class_name", "") or "").strip()
        if class_name:
            return f"All students ({class_name})"
        return "All students"

    def _parent_read_keys(self):
        if hasattr(self, "_cached_parent_read_keys"):
            return self._cached_parent_read_keys
        request = self.context.get("request")
        pp = parent_profile_for_user(getattr(request, "user", None))
        if not pp:
            self._cached_parent_read_keys = set()
            return self._cached_parent_read_keys
        self._cached_parent_read_keys = set(
            ParentNotificationRead.objects.filter(parent=pp).values_list("notification_key", flat=True)
        )
        return self._cached_parent_read_keys

    def get_is_read(self, obj):
        # Homework read-state is tracked via shared notification key format.
        return f"homework-{obj.id}" in self._parent_read_keys()

    def get_read_status(self, obj):
        return "READ" if self.get_is_read(obj) else "UNREAD"

    def get_read_count(self, obj):
        request = self.context.get("request")
        if not request or str(getattr(request.user, "role", "") or "").strip().upper() != "FRANCHISE":
            return None
        return ParentNotificationRead.objects.filter(notification_key=f"homework-{obj.id}").count()

    def get_viewed_by_parents(self, obj):
        request = self.context.get("request")
        if not request or str(getattr(request.user, "role", "") or "").strip().upper() != "FRANCHISE":
            return None
        reads = ParentNotificationRead.objects.filter(notification_key=f"homework-{obj.id}").select_related("parent", "parent__user")
        return [
            {
                "parent_id": r.parent.id,
                "parent_name": str(r.parent),
                "read_at": r.read_at,
            }
            for r in reads
        ]

    def validate_student(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        franchise = franchise_profile_for_user(getattr(request, "user", None))
        if not franchise or value.parent.franchise_id != franchise.id:
            raise serializers.ValidationError("Student is not enrolled at your centre.")
        return value


class AnnouncementSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    audience_label = serializers.SerializerMethodField()
    notification_origin = serializers.SerializerMethodField()
    schedule_date = serializers.DateField(required=False, allow_null=True, write_only=True)
    is_scheduled = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            "id",
            "franchise",
            "campaign",
            "title",
            "body",
            "student",
            "student_name",
            "class_name",
            "audience_label",
            "notification_origin",
            "published_at",
            "schedule_date",
            "is_scheduled",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "franchise",
            "campaign",
            "student_name",
            "audience_label",
            "notification_origin",
            "is_scheduled",
            "created_at",
            "updated_at",
        ]

    def get_student_name(self, obj):
        try:
            st = obj.student
        except ObjectDoesNotExist:
            return ""
        return getattr(st, "full_name", "") or ""

    def get_audience_label(self, obj):
        if obj.student_id:
            name = self.get_student_name(obj)
            return name or f"Student #{obj.student_id}"
        target_class = (obj.class_name or "").strip()
        if target_class:
            return target_class
        return "All parents"

    def get_notification_origin(self, obj) -> str:
        return "head_office" if obj.campaign_id else "centre"

    def get_is_scheduled(self, obj) -> bool:
        from django.utils import timezone

        return bool(obj.published_at and obj.published_at > timezone.now())

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not (data.get("class_name") or "").strip() and instance.student_id:
            try:
                data["class_name"] = (instance.student.class_name or "").strip()
            except ObjectDoesNotExist:
                pass
        return data

    def validate_student(self, value):
        if value is None:
            return value
        request = self.context.get("request")
        franchise = franchise_profile_for_user(getattr(request, "user", None))
        if not franchise:
            raise serializers.ValidationError("Student is not enrolled at your centre.")
        if value.parent.franchise_id == franchise.id:
            return value
        from accounts.profile_access import _franchise_for_legacy_student

        if _franchise_for_legacy_student(value) == franchise:
            return value
        raise serializers.ValidationError("Student is not enrolled at your centre.")

    def validate_class_name(self, value):
        from students.portal_views import normalize_portal_class_name

        return normalize_portal_class_name(value or "")

    def validate(self, attrs):
        from students.portal_schedule import published_at_from_schedule_date

        schedule_date = attrs.pop("schedule_date", serializers.empty)
        if "student" in attrs:
            student = attrs["student"]
        elif self.instance is not None:
            student = self.instance.student
        else:
            student = None
        if "class_name" in attrs:
            class_name = attrs["class_name"]
        elif self.instance is not None:
            class_name = self.instance.class_name
        else:
            class_name = ""
        class_name = (class_name or "").strip()
        if "class_name" in attrs or self.instance is None:
            attrs["class_name"] = class_name
        if student:
            attrs["student"] = student
        elif "student" in attrs or self.instance is not None:
            attrs["student"] = None
        if student and class_name:
            raise serializers.ValidationError("Choose either a class or a student, not both.")

        if schedule_date is not serializers.empty:
            attrs["published_at"] = published_at_from_schedule_date(schedule_date)

        if self.instance is None:
            attrs.setdefault("visible_to_parents", True)
            attrs.setdefault("visible_to_centres", False)

        return attrs


class AdminAnnouncementCampaignSerializer(serializers.ModelSerializer):
    """Head office: publish notifications to one or many centres."""

    student_name = serializers.SerializerMethodField()
    audience_label = serializers.SerializerMethodField()
    publish_target_label = serializers.SerializerMethodField()
    franchise_name = serializers.SerializerMethodField()
    schedule_date = serializers.DateField(required=False, allow_null=True, write_only=True)
    target_scope = serializers.CharField(required=False, write_only=True)
    franchise_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
    )

    class Meta:
        model = AnnouncementCampaign
        fields = [
            "id",
            "franchise",
            "franchise_name",
            "title",
            "body",
            "student",
            "student_name",
            "class_name",
            "audience_label",
            "publish_scope",
            "target_scope",
            "target_states",
            "target_cities",
            "target_franchise_ids",
            "franchise_ids",
            "publish_target_label",
            "visible_to_parents",
            "visible_to_centres",
            "published_at",
            "schedule_date",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "franchise_name",
            "student_name",
            "audience_label",
            "publish_target_label",
            "created_at",
            "updated_at",
        ]

    def get_student_name(self, obj):
        if not obj.student_id:
            return ""
        try:
            return obj.student.full_name or ""
        except ObjectDoesNotExist:
            return ""

    def get_audience_label(self, obj):
        from students.announcement_campaigns import audience_label

        return audience_label(obj)

    def get_publish_target_label(self, obj):
        from students.announcement_campaigns import publish_target_label

        return publish_target_label(obj)

    def get_franchise_name(self, obj):
        if not obj.franchise_id:
            return ""
        try:
            return obj.franchise.name or ""
        except ObjectDoesNotExist:
            return ""

    def validate_class_name(self, value):
        from students.portal_views import normalize_portal_class_name

        return normalize_portal_class_name(value or "")

    def validate_student(self, value):
        if value is None:
            return value
        franchise = self.initial_data.get("franchise")
        franchise_ids = self.initial_data.get("franchise_ids") or []
        target_scope = (self.initial_data.get("target_scope") or self.initial_data.get("publish_scope") or "").strip()
        if target_scope != AnnouncementCampaign.PublishScope.ONE_CENTRE:
            raise serializers.ValidationError("Student targeting is only available for one centre.")
        franchise_id = franchise or (franchise_ids[0] if franchise_ids else None)
        if not franchise_id:
            raise serializers.ValidationError("Select a centre before choosing a student.")
        from accounts.profile_access import students_at_franchise
        from franchises.models import Franchise

        centre = Franchise.objects.filter(pk=franchise_id).first()
        if not centre:
            raise serializers.ValidationError("Centre not found.")
        if not students_at_franchise(centre).filter(pk=value.pk).exists():
            raise serializers.ValidationError("Student is not enrolled at the selected centre.")
        return value

    def validate(self, attrs):
        from students.portal_schedule import published_at_from_schedule_date

        target_scope = (attrs.pop("target_scope", None) or attrs.get("publish_scope") or "").strip()
        if target_scope:
            attrs["publish_scope"] = target_scope

        franchise_ids = attrs.pop("franchise_ids", None)
        scope = attrs.get("publish_scope") or (
            self.instance.publish_scope if self.instance else AnnouncementCampaign.PublishScope.PAN_INDIA
        )

        if scope == AnnouncementCampaign.PublishScope.ONE_CENTRE:
            franchise = attrs.get("franchise")
            if franchise is None and self.instance is not None and "franchise" not in attrs:
                franchise = self.instance.franchise
            if franchise is None and franchise_ids:
                from franchises.models import Franchise

                franchise = Franchise.objects.filter(pk=franchise_ids[0]).first()
                if franchise:
                    attrs["franchise"] = franchise
            if not attrs.get("franchise") and not (self.instance and self.instance.franchise_id):
                raise serializers.ValidationError({"franchise": "Select a centre."})
            if attrs.get("franchise"):
                attrs["target_franchise_ids"] = [attrs["franchise"].pk]
        elif scope == AnnouncementCampaign.PublishScope.FRANCHISES:
            ids = franchise_ids if franchise_ids is not None else (self.instance.target_franchise_ids if self.instance else [])
            if not ids:
                raise serializers.ValidationError({"franchise_ids": "Select at least one centre."})
            attrs["target_franchise_ids"] = ids
            attrs["franchise"] = None
            attrs["student"] = None
        elif scope == AnnouncementCampaign.PublishScope.STATE:
            states = attrs.get("target_states")
            if states is None and self.instance is not None:
                states = self.instance.target_states
            if not states:
                raise serializers.ValidationError({"target_states": "Select at least one state."})
            attrs["franchise"] = None
            attrs["student"] = None
        elif scope == AnnouncementCampaign.PublishScope.CITY:
            cities = attrs.get("target_cities")
            if cities is None and self.instance is not None:
                cities = self.instance.target_cities
            if not cities:
                raise serializers.ValidationError({"target_cities": "Select at least one city."})
            attrs["franchise"] = None
            attrs["student"] = None
        else:
            attrs["franchise"] = None
            attrs["student"] = None

        student = attrs.get("student")
        if student is None and self.instance is not None and "student" not in attrs:
            student = self.instance.student
        class_name = attrs.get("class_name")
        if class_name is None and self.instance is not None and "class_name" not in attrs:
            class_name = self.instance.class_name
        if (student and (class_name or "").strip()) or (
            student and scope != AnnouncementCampaign.PublishScope.ONE_CENTRE
        ):
            if student and (class_name or "").strip():
                raise serializers.ValidationError("Choose either a class filter or one student, not both.")
            if student and scope != AnnouncementCampaign.PublishScope.ONE_CENTRE:
                raise serializers.ValidationError("Student targeting is only available for one centre.")

        schedule_date = attrs.pop("schedule_date", serializers.empty)
        if schedule_date is not serializers.empty:
            attrs["published_at"] = published_at_from_schedule_date(schedule_date)

        return attrs

    def create(self, validated_data):
        from students.announcement_campaigns import sync_campaign_deliveries
        from students.portal_views import _after_announcement_saved

        campaign = AnnouncementCampaign.objects.create(**validated_data)
        sync_campaign_deliveries(campaign, after_save=_after_announcement_saved)
        return campaign

    def update(self, instance, validated_data):
        from students.announcement_campaigns import sync_campaign_deliveries
        from students.portal_views import _after_announcement_saved

        for key, val in validated_data.items():
            setattr(instance, key, val)
        instance.save()
        sync_campaign_deliveries(instance, after_save=_after_announcement_saved)
        return instance


class AttendanceRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceRecord
        fields = [
            "id",
            "student",
            "student_name",
            "class_name",
            "date",
            "status",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "student_name", "class_name", "created_at", "updated_at"]

    def get_student_name(self, obj):
        try:
            st = obj.student
        except ObjectDoesNotExist:
            return ""
        return getattr(st, "full_name", "") or ""

    def get_class_name(self, obj):
        try:
            st = obj.student
        except ObjectDoesNotExist:
            return ""
        return (getattr(st, "class_name", None) or "").strip()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # ``student`` is the StudentProfile pk; expose ``student_id`` alias for mobile clients.
        if data.get("student") is not None:
            data["student_id"] = data["student"]
        return data

    def validate_student(self, value):
        request = self.context.get("request")
        franchise = franchise_profile_for_user(getattr(request, "user", None))
        if not franchise or value.parent.franchise_id != franchise.id:
            raise serializers.ValidationError("Student is not enrolled at your centre.")
        return value


class FranchiseAttendanceUpsertSerializer(AttendanceRecordSerializer):
    """Franchise save updates existing student+date rows; skip create-time unique checks."""

    class Meta(AttendanceRecordSerializer.Meta):
        validators = []


class FranchiseAttendanceBulkItemSerializer(serializers.Serializer):
    student = serializers.PrimaryKeyRelatedField(queryset=StudentProfile.objects.all())
    date = serializers.DateField()
    status = serializers.ChoiceField(choices=AttendanceRecord.Status.choices)
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_student(self, value):
        request = self.context.get("request")
        franchise = franchise_profile_for_user(getattr(request, "user", None))
        if not franchise or value.parent.franchise_id != franchise.id:
            raise serializers.ValidationError("Student is not enrolled at your centre.")
        return value


class FranchiseAttendanceBulkSerializer(serializers.Serializer):
    records = FranchiseAttendanceBulkItemSerializer(many=True, allow_empty=False)


class FeeRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)

    class Meta:
        model = FeeRecord
        fields = [
            "id",
            "student",
            "student_name",
            "source",
            "line_serial",
            "fee_structure_name",
            "id_card_no",
            "course",
            "title",
            "amount",
            "discount",
            "amount_paid",
            "due_date",
            "paid_on",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "student_name", "source", "line_serial", "created_at", "updated_at"]

    def validate_student(self, value):
        request = self.context.get("request")
        franchise = franchise_profile_for_user(getattr(request, "user", None))
        if not franchise or value.parent.franchise_id != franchise.id:
            raise serializers.ValidationError("Student is not enrolled at your centre.")
        return value


class SupportTicketParentSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    student_class_name = serializers.SerializerMethodField()

    class Meta:
        model = SupportTicket
        fields = [
            "id",
            "subject",
            "body",
            "status",
            "franchise_reply",
            "student",
            "student_name",
            "student_class_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "status",
            "franchise_reply",
            "student_name",
            "student_class_name",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {"student": {"required": False, "allow_null": True}}

    def _student_fields(self, obj):
        if not obj.student_id:
            return None, None
        try:
            student = obj.student
        except ObjectDoesNotExist:
            return None, None
        name = (student.full_name or "").strip().rstrip("-").strip()
        cls = (student.class_name or "").strip() or None
        return name or None, cls

    def get_student_name(self, obj):
        name, _cls = self._student_fields(obj)
        return name

    def get_student_class_name(self, obj):
        _name, cls = self._student_fields(obj)
        return cls


class SupportTicketFranchiseSerializer(serializers.ModelSerializer):
    """Franchise ticket list; parent.user may be missing on live DB — avoid source= traversal."""

    status = serializers.ChoiceField(
        choices=[
            SupportTicket.Status.OPEN,
            SupportTicket.Status.IN_PROGRESS,
            SupportTicket.Status.CLOSED,
            ("RESOLVED", "Resolved"),
        ]
    )
    parent_name = serializers.SerializerMethodField()
    parent_email = serializers.SerializerMethodField()
    student_name = serializers.SerializerMethodField()
    student_class_name = serializers.SerializerMethodField()

    class Meta:
        model = SupportTicket
        fields = [
            "id",
            "parent",
            "parent_name",
            "parent_email",
            "student",
            "student_name",
            "student_class_name",
            "subject",
            "body",
            "status",
            "franchise_reply",
            "ho_reminder_message",
            "ho_reminded_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "parent",
            "parent_name",
            "parent_email",
            "student",
            "student_name",
            "student_class_name",
            "subject",
            "body",
            "ho_reminder_message",
            "ho_reminded_at",
            "created_at",
        ]

    def _student_fields(self, obj):
        if not obj.student_id:
            return None, None
        try:
            student = obj.student
        except ObjectDoesNotExist:
            return None, None
        name = (student.full_name or "").strip().rstrip("-").strip()
        cls = (student.class_name or "").strip() or None
        return name or None, cls

    def get_student_name(self, obj):
        name, _cls = self._student_fields(obj)
        return name

    def get_student_class_name(self, obj):
        _name, cls = self._student_fields(obj)
        return cls

    def validate_status(self, value):
        # Frontend uses "RESOLVED" while DB keeps legacy "CLOSED".
        if str(value or "").upper() == "RESOLVED":
            return SupportTicket.Status.CLOSED
        return value

    def get_parent_name(self, obj):
        try:
            parent = obj.parent
        except ObjectDoesNotExist:
            return ""
        try:
            user = parent.user
        except ObjectDoesNotExist:
            return ""
        name = (getattr(user, "full_name", None) or "").strip()
        return name or getattr(user, "email", "") or ""

    def get_parent_email(self, obj):
        try:
            parent = obj.parent
        except ObjectDoesNotExist:
            return ""
        try:
            user = parent.user
        except ObjectDoesNotExist:
            return ""
        return getattr(user, "email", "") or ""


class SupportTicketAdminSerializer(serializers.ModelSerializer):
    """Head-office CMS: all centres, filters, HO reminder fields."""

    franchise = serializers.SerializerMethodField()
    franchise_name = serializers.SerializerMethodField()
    parent_name = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    is_unresolved = serializers.SerializerMethodField()
    days_open = serializers.SerializerMethodField()

    class Meta:
        model = SupportTicket
        fields = [
            "id",
            "franchise",
            "franchise_name",
            "parent_name",
            "subject",
            "body",
            "status",
            "status_label",
            "is_unresolved",
            "days_open",
            "franchise_reply",
            "ho_reminder_message",
            "ho_reminded_at",
            "created_at",
            "updated_at",
        ]

    def get_franchise(self, obj):
        try:
            parent = obj.parent
        except ObjectDoesNotExist:
            return None
        return getattr(parent, "franchise_id", None)

    def get_franchise_name(self, obj):
        try:
            parent = obj.parent
        except ObjectDoesNotExist:
            return ""
        try:
            franchise = parent.franchise
        except ObjectDoesNotExist:
            return ""
        return (getattr(franchise, "name", None) or "").strip()

    def get_parent_name(self, obj):
        try:
            parent = obj.parent
        except ObjectDoesNotExist:
            return ""
        try:
            user = parent.user
        except ObjectDoesNotExist:
            return ""
        name = (getattr(user, "full_name", None) or "").strip()
        return name or getattr(user, "email", "") or ""

    def get_status_label(self, obj):
        if obj.status == SupportTicket.Status.CLOSED:
            return "Resolved"
        if obj.status == SupportTicket.Status.IN_PROGRESS:
            return "In progress"
        if obj.status == SupportTicket.Status.OPEN:
            return "Open"
        return str(obj.status or "").replace("_", " ").title()

    def get_is_unresolved(self, obj):
        return obj.status != SupportTicket.Status.CLOSED

    def get_days_open(self, obj):
        if not obj.created_at:
            return 0
        from django.utils import timezone

        delta = timezone.now() - obj.created_at
        return max(0, delta.days)


class TransportRouteSerializer(serializers.ModelSerializer):
    driver_token = serializers.SerializerMethodField()
    driver_info = serializers.SerializerMethodField()

    class Meta:
        model = TransportRoute
        fields = [
            "id",
            "franchise",
            "route_name",
            "description",
            "map_url",
            "vehicle_number",
            "driver_name",
            "driver_phone",
            "driver_profile",
            "driver_info",
            "driver_token",
            "tracking_note",
            "destination",
            "destination_latitude",
            "destination_longitude",
            "sort_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "franchise", "driver_token", "driver_info", "created_at", "updated_at"]

    def get_driver_info(self, obj):
        if obj.driver_profile:
            return {
                "id": obj.driver_profile.id,
                "full_name": obj.driver_profile.user.full_name,
                "email": obj.driver_profile.user.email,
                "phone": obj.driver_profile.phone,
                "service_number": (obj.driver_profile.service_number or "").strip(),
            }
        return None

    def get_driver_token(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if str(getattr(user, "role", "") or "").strip().upper() == "FRANCHISE":
            return str(obj.driver_token)
        return ""


class ParentTransportRouteSerializer(serializers.ModelSerializer):
    """Slim route payload for parent apps — only fields the centre actually configures."""

    driver_info = serializers.SerializerMethodField()

    class Meta:
        model = TransportRoute
        fields = ["id", "route_name", "driver_info"]

    def get_driver_info(self, obj):
        if not obj.driver_profile_id:
            return None
        profile = obj.driver_profile
        return {
            "id": profile.id,
            "full_name": profile.user.full_name,
            "email": profile.user.email,
            "phone": profile.phone,
            "service_number": (profile.service_number or "").strip(),
        }


def serialize_parent_trip_location(location):
    if not location:
        return None
    payload = {
        "latitude": float(location.latitude),
        "longitude": float(location.longitude),
        "recorded_at": location.recorded_at,
    }
    if location.heading is not None:
        payload["heading"] = float(location.heading)
    return payload


def serialize_parent_live_trip(trip):
    locations = list(trip.locations.order_by("-recorded_at")[:50])
    return {
        "id": trip.id,
        "trip_type": trip.trip_type,
        "status": trip.status,
        "started_at": trip.started_at,
        "recent_locations": [
            {"latitude": float(loc.latitude), "longitude": float(loc.longitude)}
            for loc in locations
        ],
    }


def serialize_parent_trip_student_status(student_status):
    if not student_status:
        return None
    return {
        "student_id": student_status.student_id,
        "student_name": student_status.student.full_name,
        "status": student_status.status,
        "note": student_status.note or "",
        "updated_at": student_status.updated_at,
    }


class StudentTransportAssignmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    route_name = serializers.CharField(source="route.route_name", read_only=True)

    class Meta:
        model = StudentTransportAssignment
        fields = [
            "id",
            "student",
            "student_name",
            "route",
            "route_name",
            "pickup_stop",
            "pickup_latitude",
            "pickup_longitude",
            "drop_stop",
            "drop_latitude",
            "drop_longitude",
            "pickup_time",
            "drop_time",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "student_name", "route_name", "created_at", "updated_at"]

    def validate_student(self, value):
        request = self.context.get("request")
        franchise = franchise_profile_for_user(getattr(request, "user", None))
        if not franchise or value.parent.franchise_id != franchise.id:
            raise serializers.ValidationError("Student is not enrolled at your centre.")
        return value

    def validate_route(self, value):
        request = self.context.get("request")
        franchise = franchise_profile_for_user(getattr(request, "user", None))
        if not franchise or value.franchise_id != franchise.id:
            raise serializers.ValidationError("Route does not belong to your centre.")
        return value


class TransportTripLocationSerializer(serializers.ModelSerializer):
    speed = serializers.FloatField(allow_null=True, required=False)
    heading = serializers.FloatField(allow_null=True, required=False)
    accuracy = serializers.FloatField(allow_null=True, required=False)

    class Meta:
        model = TransportTripLocation
        fields = ["id", "latitude", "longitude", "speed", "heading", "accuracy", "recorded_at"]
        read_only_fields = ["id", "recorded_at"]


class TransportTripSerializer(serializers.ModelSerializer):
    route_name = serializers.CharField(source="route.route_name", read_only=True)
    vehicle_number = serializers.CharField(source="route.vehicle_number", read_only=True)
    driver_name = serializers.SerializerMethodField()
    driver_phone = serializers.SerializerMethodField()
    destination = serializers.CharField(source="route.destination", read_only=True)
    destination_latitude = serializers.DecimalField(source="route.destination_latitude", max_digits=22, decimal_places=16, read_only=True)
    destination_longitude = serializers.DecimalField(source="route.destination_longitude", max_digits=22, decimal_places=16, read_only=True)
    latest_location = serializers.SerializerMethodField()
    recent_locations = serializers.SerializerMethodField()

    class Meta:
        model = TransportTrip
        fields = [
            "id",
            "route",
            "route_name",
            "vehicle_number",
            "destination",
            "driver_name",
            "driver_phone",
            "trip_type",
            "status",
            "started_at",
            "completed_at",
            "latest_location",
            "recent_locations",
            "destination_latitude",
            "destination_longitude",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "started_at", "completed_at", "latest_location", "created_at", "updated_at"]

    def get_driver_name(self, obj):
        if obj.route.driver_profile:
            return obj.route.driver_profile.user.full_name
        return obj.route.driver_name

    def get_driver_phone(self, obj):
        if obj.route.driver_profile:
            return obj.route.driver_profile.phone
        return obj.route.driver_phone

    def get_latest_location(self, obj):
        latest = obj.locations.order_by("-recorded_at").first()
        if not latest:
            return None
        return TransportTripLocationSerializer(latest).data

    def get_recent_locations(self, obj):
        # Return last 50 locations for polyline drawing
        locations = obj.locations.order_by("-recorded_at")[:50]
        return TransportTripLocationSerializer(locations, many=True).data
