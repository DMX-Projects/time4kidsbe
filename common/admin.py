from django.contrib import admin
from .models import HeroSlide, HomeTestimonial, HomePageContent


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ('id', 'alt_text', 'order', 'is_active', 'created_at')
    list_editable = ('order', 'is_active')
    search_fields = ('alt_text',)


@admin.register(HomeTestimonial)
class HomeTestimonialAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "relation", "order", "is_active", "updated_at")
    list_editable = ("order", "is_active")
    search_fields = ("author", "text", "relation")


@admin.register(HomePageContent)
class HomePageContentAdmin(admin.ModelAdmin):
    list_display = ("id", "updated_at")

    def get_queryset(self, request):
        # Changelist only needs id/updated_at; avoid loading large JSON blobs on every row.
        return super().get_queryset(request).defer("data")

    def has_add_permission(self, request):
        if HomePageContent.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        # Singleton: avoid accidental deletes; superusers can still remove duplicates.
        if getattr(request.user, "is_superuser", False):
            return super().has_delete_permission(request, obj)
        return False
