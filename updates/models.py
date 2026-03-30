from django.db import models
from franchises.models import Franchise

class Update(models.Model):
    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE, related_name="updates", null=True, blank=True)
    text = models.TextField()
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.franchise.name} - {self.date} - {self.text[:50]}"


class SocialMediaUpload(models.Model):
    """
    Franchise users upload brand-safe posts/files.
    Admin can approve/reject; franchise sees status.
    """

    MEDIA_TYPE_CHOICES = (
        ("image", "Image"),
        ("video", "Video"),
    )

    STATUS_CHOICES = (
        ("pending", "Pending Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    franchise = models.ForeignKey(
        Franchise,
        on_delete=models.CASCADE,
        related_name="social_media_uploads",
    )
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default="image")
    title = models.CharField(max_length=200, blank=True)
    caption = models.TextField(blank=True)
    file = models.FileField(upload_to="social_media_uploads/")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    admin_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.franchise.name} - {self.title or self.file.name} ({self.status})"
