from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from accounts.profile_access import franchise_profile_for_user, parent_profile_for_user
from franchises.models import ParentProfile

from .models import (
    Announcement,
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

    class Meta:
        model = StudentProfile
        fields = ['id', 'parent', 'first_name', 'last_name', 'full_name', 'class_name', 'section',
                  'roll_number', 'date_of_birth', 'admission_date', 'profile_picture',
                  'is_active', 'blood_group', 'emergency_contact', 'parent_info', 'grades_count', 'created_at', 'updated_at']
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
        fields = ["id", "full_name", "class_name", "roll_number"]


class FranchiseStudentSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()
    parent = serializers.PrimaryKeyRelatedField(queryset=ParentProfile.objects.all())

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
            "roll_number",
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
    class Meta:
        model = Announcement
        fields = [
            "id",
            "franchise",
            "title",
            "body",
            "published_at",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "franchise", "created_at", "updated_at"]


class AttendanceRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceRecord
        fields = [
            "id",
            "student",
            "student_name",
            "date",
            "status",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "student_name", "created_at", "updated_at"]

    def get_student_name(self, obj):
        try:
            st = obj.student
        except ObjectDoesNotExist:
            return ""
        return getattr(st, "full_name", "") or ""

    def validate_student(self, value):
        request = self.context.get("request")
        franchise = franchise_profile_for_user(getattr(request, "user", None))
        if not franchise or value.parent.franchise_id != franchise.id:
            raise serializers.ValidationError("Student is not enrolled at your centre.")
        return value


class FeeRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)

    class Meta:
        model = FeeRecord
        fields = [
            "id",
            "student",
            "student_name",
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
        read_only_fields = ["id", "student_name", "created_at", "updated_at"]

    def validate_student(self, value):
        request = self.context.get("request")
        franchise = franchise_profile_for_user(getattr(request, "user", None))
        if not franchise or value.parent.franchise_id != franchise.id:
            raise serializers.ValidationError("Student is not enrolled at your centre.")
        return value


class SupportTicketParentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ["id", "subject", "body", "status", "franchise_reply", "created_at", "updated_at"]
        read_only_fields = ["status", "franchise_reply", "created_at", "updated_at"]


class SupportTicketFranchiseSerializer(serializers.ModelSerializer):
    """Franchise ticket list; parent.user may be missing on live DB — avoid source= traversal."""

    parent_name = serializers.SerializerMethodField()
    parent_email = serializers.SerializerMethodField()

    class Meta:
        model = SupportTicket
        fields = [
            "id",
            "parent",
            "parent_name",
            "parent_email",
            "subject",
            "body",
            "status",
            "franchise_reply",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["parent", "parent_name", "parent_email", "subject", "body", "created_at"]

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
            }
        return None

    def get_driver_token(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if str(getattr(user, "role", "") or "").strip().upper() == "FRANCHISE":
            return str(obj.driver_token)
        return ""


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
