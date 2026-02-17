from django.contrib import admin
from .models import StudentProfile, Grade


class GradeInline(admin.TabularInline):
    """Inline grades for student profile"""
    model = Grade
    extra = 1
    fields = ('subject', 'exam_type', 'marks_obtained', 'total_marks', 'grade', 'exam_date', 'remarks')
    readonly_fields = ('created_at',)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'class_name', 'parent', 'is_active', 'created_at')
    list_filter = ('is_active', 'class_name', 'created_at', 'parent__franchise')
    search_fields = ('first_name', 'last_name', 'roll_number', 'parent__user__email', 'parent__user__full_name')
    list_editable = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [GradeInline]
    
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
    list_display = ('student', 'subject', 'exam_type', 'marks_obtained', 'total_marks', 'grade', 'get_percentage', 'exam_date')
    list_filter = ('exam_type', 'exam_date', 'subject', 'student__parent__franchise')
    search_fields = ('student__first_name', 'student__last_name', 'subject', 'student__parent__user__email')
    readonly_fields = ('created_at', 'updated_at', 'get_percentage')
    
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

