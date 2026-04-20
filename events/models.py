from django.conf import settings
from django.db import models

from franchises.models import Franchise


class Event(models.Model):
    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE, related_name="events")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="events_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "title"]

    def __str__(self) -> str:
        title = (self.title or "").strip() or "(untitled)"
        if not self.franchise_id:
            return f"{title} (no franchise)"
        try:
            franchise_label = self.franchise.name
        except Franchise.DoesNotExist:
            franchise_label = f"missing franchise #{self.franchise_id}"
        return f"{title} ({franchise_label})"


class EventMedia(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = "IMAGE", "Image"
        VIDEO = "VIDEO", "Video"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="media")
    file = models.FileField(upload_to="events/media/")
    media_type = models.CharField(max_length=10, choices=MediaType.choices, default=MediaType.IMAGE)
    caption = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="media_uploaded"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        if not self.event_id:
            return "Event media (unsaved)"
        try:
            ev = self.event
        except Event.DoesNotExist:
            return f"Event media (missing event #{self.event_id})"
        etitle = (ev.title or "").strip() or "(untitled)"
        return f"Media for {etitle}"
