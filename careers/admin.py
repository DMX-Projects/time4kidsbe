from django.contrib import admin

from .models import Career


@admin.register(Career)
class CareerAdmin(admin.ModelAdmin):
    list_display = ("title", "admin", "location", "is_active", "created_at")
    search_fields = ("title", "location", "admin__email")
    list_filter = ("is_active",)
