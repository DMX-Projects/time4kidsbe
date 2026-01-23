from django.contrib import admin

from .models import Career, JobApplication


@admin.register(Career)
class CareerAdmin(admin.ModelAdmin):
    list_display = ("title", "admin", "location", "is_active", "created_at")
    search_fields = ("title", "location", "admin__email")
    list_filter = ("is_active",)


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "get_career_title", "status", "applied_at")
    search_fields = ("full_name", "email", "phone", "career__title")
    list_filter = ("status", "applied_at", "career")
    readonly_fields = ("applied_at", "updated_at")
    
    def get_career_title(self, obj):
        return obj.career.title
    get_career_title.short_description = "Position"
