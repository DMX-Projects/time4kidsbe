from django.contrib import admin

from .models import Franchise, ParentProfile, FranchiseLocation


@admin.register(FranchiseLocation)
class FranchiseLocationAdmin(admin.ModelAdmin):
    list_display = ['city_name', 'state', 'is_active', 'display_order']
    list_filter = ['is_active', 'state']
    search_fields = ['city_name']
    list_editable = ("is_active", "display_order")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("display_order", "city_name")


@admin.register(Franchise)
class FranchiseAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "admin", "user", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "city", "admin__email", "user__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "franchise", "child_name", "created_at")
    list_filter = ("franchise",)
    search_fields = ("user__email", "user__full_name", "child_name")
    list_filter = ("franchise",)
