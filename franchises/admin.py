from django.contrib import admin

from .models import Franchise, ParentProfile


@admin.register(Franchise)
class FranchiseAdmin(admin.ModelAdmin):
    list_display = ("name", "admin", "user", "city", "is_active")
    search_fields = ("name", "slug", "admin__email", "user__email")
    list_filter = ("city", "is_active")


@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "franchise", "child_name")
    search_fields = ("user__email", "franchise__name")
    list_filter = ("franchise",)
