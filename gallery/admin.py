from django.contrib import admin
from .models import MediaItem

@admin.register(MediaItem)
class MediaItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'media_type', 'created_at')
    list_filter = ('media_type', 'created_at')
    search_fields = ('title',)
