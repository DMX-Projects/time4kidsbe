from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from accounts.profile_access import franchise_profile_for_user
from franchises.models import ParentProfile

from .models import (
    Announcement,
    AttendanceRecord,
    FeeRecord,
    Grade,
    HomeworkAssignment,
    StudentAchievement,
    StudentProfile,
    SupportTicket,
    TransportRoute,
)
from common.fields import RelativeImageField


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
        fields = ['id', 'parent', 'first_name', 'last_name', 'full_name', 'class_name', 
                  'roll_number', 'date_of_birth', 'admission_date', 'profile_picture',
                  'is_active', 'parent_info', 'grades_count', 'created_at', 'updated_at']
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
            "roll_number",
            "date_of_birth",
            "admission_date",
            "is_active",
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
    student_name = serializers.CharField(source="student.full_name", read_only=True)

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
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "franchise", "created_at", "updated_at", "student_name"]

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
            "title",
            "amount",
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
    class Meta:
        model = TransportRoute
        fields = [
            "id",
            "franchise",
            "route_name",
            "description",
            "map_url",
            "tracking_note",
            "sort_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "franchise", "created_at", "updated_at"]

