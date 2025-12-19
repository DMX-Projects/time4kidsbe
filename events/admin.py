from django.contrib import admin

from .models import Event, EventMedia


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "franchise", "start_date", "end_date")
    list_filter = ("franchise", "start_date")
    search_fields = ("title", "description", "franchise__name")


@admin.register(EventMedia)
class EventMediaAdmin(admin.ModelAdmin):
    list_display = ("event", "media_type", "uploaded_at")
    list_filter = ("media_type",)
    search_fields = ("event__title",)
