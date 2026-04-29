from django.contrib import admin

from franchises.models import Franchise, ParentProfile

from .models import (
    Announcement,
    AttendanceRecord,
    FeeRecord,
    Grade,
    HomeworkAssignment,
    StudentAchievement,
    StudentProfile,
    StudentTransportAssignment,
    StudentTripStatus,
    SupportTicket,
    TransportRoute,
    TransportTrip,
    TransportTripLocation,
)


class GradeInline(admin.TabularInline):
    """Inline grades for student profile"""
    model = Grade
    extra = 1
    fields = ('subject', 'exam_type', 'marks_obtained', 'total_marks', 'grade', 'exam_date', 'remarks')
    readonly_fields = ('created_at',)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "class_name", "display_parent", "is_active", "created_at")
    list_filter = ('is_active', 'class_name', 'created_at', 'parent__franchise')
    search_fields = ('first_name', 'last_name', 'roll_number', 'parent__user__email', 'parent__user__full_name')
    list_editable = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [GradeInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "parent",
            "parent__user",
            "parent__franchise",
        )

    def display_parent(self, obj: StudentProfile):
        if not obj.parent_id:
            return "—"
        try:
            return str(obj.parent)
        except ParentProfile.DoesNotExist:
            return f"(missing parent #{obj.parent_id})"

    display_parent.short_description = "Parent"
    
    fieldsets = (
        ('Student Information', {
            'fields': ('parent', 'first_name', 'last_name', 'class_name', 'roll_number')
        }),
        ('Additional Details', {
            'fields': ('date_of_birth', 'admission_date', 'profile_picture', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = (
        "display_student",
        "subject",
        "exam_type",
        "marks_obtained",
        "total_marks",
        "grade",
        "get_percentage",
        "exam_date",
    )
    list_filter = ('exam_type', 'exam_date', 'subject', 'student__parent__franchise')
    search_fields = ('student__first_name', 'student__last_name', 'subject', 'student__parent__user__email')
    readonly_fields = ('created_at', 'updated_at', 'get_percentage')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "student",
            "student__parent",
            "student__parent__franchise",
        )

    def display_student(self, obj: Grade):
        if not obj.student_id:
            return "—"
        try:
            return str(obj.student)
        except StudentProfile.DoesNotExist:
            return f"(missing student #{obj.student_id})"

    display_student.short_description = "Student"
    
    fieldsets = (
        ('Grade Information', {
            'fields': ('student', 'subject', 'exam_type', 'exam_date')
        }),
        ('Marks & Grade', {
            'fields': ('marks_obtained', 'total_marks', 'grade', 'get_percentage', 'remarks')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_percentage(self, obj):
        return f"{obj.percentage}%"
    get_percentage.short_description = 'Percentage'


@admin.register(StudentAchievement)
class StudentAchievementAdmin(admin.ModelAdmin):
    list_display = ("title", "display_franchise", "display_student", "achieved_date", "created_at")
    list_filter = ("franchise", "achieved_date")
    search_fields = ("title", "notes", "student__first_name", "student__last_name")
    raw_id_fields = ("student",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("franchise", "student")

    def display_franchise(self, obj: StudentAchievement):
        if not obj.franchise_id:
            return "—"
        try:
            return obj.franchise.name
        except Franchise.DoesNotExist:
            return f"(missing franchise #{obj.franchise_id})"

    display_franchise.short_description = "Franchise"

    def display_student(self, obj: StudentAchievement):
        if not obj.student_id:
            return "—"
        try:
            return str(obj.student)
        except StudentProfile.DoesNotExist:
            return f"(missing student #{obj.student_id})"

    display_student.short_description = "Student"


@admin.register(HomeworkAssignment)
class HomeworkAssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "display_franchise", "assigned_date", "display_student", "class_name")
    list_filter = ("franchise", "assigned_date")
    raw_id_fields = ("student",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("franchise", "student")

    def display_franchise(self, obj: HomeworkAssignment):
        if not obj.franchise_id:
            return "—"
        try:
            return obj.franchise.name
        except Franchise.DoesNotExist:
            return f"(missing franchise #{obj.franchise_id})"

    display_franchise.short_description = "Franchise"

    def display_student(self, obj: HomeworkAssignment):
        if not obj.student_id:
            return "—"
        try:
            return str(obj.student)
        except StudentProfile.DoesNotExist:
            return f"(missing student #{obj.student_id})"

    display_student.short_description = "Student"


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "display_franchise", "published_at", "is_active")
    list_filter = ("franchise", "is_active")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("franchise")

    def display_franchise(self, obj):
        if not obj.franchise_id:
            return "—"
        try:
            return obj.franchise.name
        except Franchise.DoesNotExist:
            return f"(missing franchise #{obj.franchise_id})"

    display_franchise.short_description = "Franchise"


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("display_student", "date", "status")
    list_filter = ("status", "date", "student__parent__franchise")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "student",
            "student__parent",
            "student__parent__franchise",
        )

    def display_student(self, obj: AttendanceRecord):
        if not obj.student_id:
            return "—"
        try:
            return str(obj.student)
        except StudentProfile.DoesNotExist:
            return f"(missing student #{obj.student_id})"

    display_student.short_description = "Student"


@admin.register(FeeRecord)
class FeeRecordAdmin(admin.ModelAdmin):
    list_display = ("title", "display_student", "amount", "due_date", "status")
    list_filter = ("status", "student__parent__franchise")
    raw_id_fields = ("student",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "student",
            "student__parent",
            "student__parent__franchise",
        )

    def display_student(self, obj: FeeRecord):
        if not obj.student_id:
            return "—"
        try:
            return str(obj.student)
        except StudentProfile.DoesNotExist:
            return f"(missing student #{obj.student_id})"

    display_student.short_description = "Student"


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("subject", "display_parent", "status", "created_at")
    list_filter = ("status", "parent__franchise")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "parent",
            "parent__user",
            "parent__franchise",
        )

    def display_parent(self, obj: SupportTicket):
        if not obj.parent_id:
            return "—"
        try:
            return str(obj.parent)
        except ParentProfile.DoesNotExist:
            return f"(missing parent #{obj.parent_id})"

    display_parent.short_description = "Parent"


@admin.register(TransportRoute)
class TransportRouteAdmin(admin.ModelAdmin):
    list_display = ("route_name", "display_franchise", "vehicle_number", "driver_name", "sort_order")
    list_filter = ("franchise",)
    readonly_fields = ("driver_token", "created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("franchise")

    def display_franchise(self, obj: TransportRoute):
        if not obj.franchise_id:
            return "—"
        try:
            return obj.franchise.name
        except Franchise.DoesNotExist:
            return f"(missing franchise #{obj.franchise_id})"

    display_franchise.short_description = "Franchise"


@admin.register(StudentTransportAssignment)
class StudentTransportAssignmentAdmin(admin.ModelAdmin):
    list_display = ("display_student", "route", "pickup_stop", "drop_stop", "is_active")
    list_filter = ("route__franchise", "route", "is_active")
    raw_id_fields = ("student", "route")

    def display_student(self, obj: StudentTransportAssignment):
        if not obj.student_id:
            return "—"
        try:
            return obj.student.full_name
        except StudentProfile.DoesNotExist:
            return f"(missing student #{obj.student_id})"

    display_student.short_description = "Student"


class TransportTripLocationInline(admin.TabularInline):
    model = TransportTripLocation
    extra = 0
    readonly_fields = ("latitude", "longitude", "speed", "heading", "accuracy", "recorded_at")
    can_delete = False


@admin.register(TransportTrip)
class TransportTripAdmin(admin.ModelAdmin):
    list_display = ("route", "trip_type", "status", "started_at", "completed_at")
    list_filter = ("status", "trip_type", "route__franchise")
    readonly_fields = ("created_at", "updated_at")
    inlines = [TransportTripLocationInline]


@admin.register(StudentTripStatus)
class StudentTripStatusAdmin(admin.ModelAdmin):
    list_display = ("trip", "display_student", "status", "updated_at")
    list_filter = ("status", "trip__route__franchise")
    raw_id_fields = ("trip", "student")

    def display_student(self, obj: StudentTripStatus):
        if not obj.student_id:
            return "—"
        try:
            return obj.student.full_name
        except StudentProfile.DoesNotExist:
            return f"(missing student #{obj.student_id})"

    display_student.short_description = "Student"

