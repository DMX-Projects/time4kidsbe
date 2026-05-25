from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import ParentRegistration, User


@admin.register(ParentRegistration)
class ParentRegistrationAdmin(admin.ModelAdmin):
    list_display = (
        "parent_name",
        "email",
        "phone",
        "child_name",
        "city",
        "display_franchise",
        "status",
        "created_at",
    )
    list_filter = ("status", "franchise", "created_at")
    search_fields = ("parent_name", "email", "phone", "child_name", "city")
    readonly_fields = ("created_at",)
    raw_id_fields = ("user", "franchise")

    @admin.display(description="Centre")
    def display_franchise(self, obj: ParentRegistration) -> str:
        if not obj.franchise_id:
            return "—"
        try:
            return obj.franchise.name
        except Exception:
            return f"#{obj.franchise_id}"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = ("email", "full_name", "role", "is_active", "is_staff")
    list_filter = ("role", "is_staff", "is_active")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("full_name", "role")}),
        (
            _("Permissions"),
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "role", "password1", "password2", "is_staff", "is_superuser"),
            },
        ),
    )

    search_fields = ("email", "full_name")
    filter_horizontal = ("groups", "user_permissions")
