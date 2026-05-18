from django.contrib import admin

from .models import GallerySection, MediaItem


class MediaItemInline(admin.TabularInline):
    model = MediaItem
    extra = 0
    fields = ("title", "media_type", "file", "embed_url", "order")


@admin.register(GallerySection)
class GallerySectionAdmin(admin.ModelAdmin):
    list_display = ("title", "order", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("title",)
    prepopulated_fields = {"slug": ("title",)}
    inlines = [MediaItemInline]


@admin.register(MediaItem)
class MediaItemAdmin(admin.ModelAdmin):
    list_display = ("title", "section", "media_type", "category", "order", "created_at")
    list_filter = ("media_type", "category", "section")
    search_fields = ("title", "caption", "author")
    raw_id_fields = ("section",)
