from django.contrib import admin

from accounts.models import User

from .models import Franchise, FranchiseLocation, ParentProfile


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
    list_display = ("name", "city", "display_admin", "display_user", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "city", "admin__email", "user__email")
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("admin", "user")

    def display_admin(self, obj: Franchise):
        if not obj.admin_id:
            return "—"
        try:
            return obj.admin.email
        except User.DoesNotExist:
            return f"(missing user #{obj.admin_id})"

    display_admin.short_description = "Admin"

    def display_user(self, obj: Franchise):
        if not obj.user_id:
            return "—"
        try:
            return obj.user.email
        except User.DoesNotExist:
            return f"(missing user #{obj.user_id})"

    display_user.short_description = "Franchise login (user)"


@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ("display_user", "display_franchise", "child_name", "created_at")
    list_filter = ("franchise",)
    search_fields = ("user__email", "user__full_name", "child_name")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "franchise")

    def display_user(self, obj: ParentProfile):
        if not obj.user_id:
            return "—"
        try:
            u = obj.user
            return (u.full_name or "").strip() or u.email
        except User.DoesNotExist:
            return f"(missing user #{obj.user_id})"

    display_user.short_description = "User"

    def display_franchise(self, obj: ParentProfile):
        if not obj.franchise_id:
            return "—"
        try:
            return obj.franchise.name
        except Franchise.DoesNotExist:
            return f"(missing franchise #{obj.franchise_id})"

    display_franchise.short_description = "Franchise"
