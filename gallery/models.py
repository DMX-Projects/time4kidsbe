from django.db import models
from django.utils.text import slugify


class GallerySection(models.Model):
    """Public gallery album heading (Photo / Video Gallery)."""

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "title"]
        verbose_name = "Gallery heading"
        verbose_name_plural = "Gallery headings"

    def save(self, *args, **kwargs):
        if not (self.slug or "").strip():
            self.slug = slugify(self.title)[:220] or "gallery-section"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.title


class MediaItem(models.Model):
    MEDIA_TYPES = (
        ("image", "Image"),
        ("video", "Video"),
        ("embed", "Embed (iframe)"),
    )

    MEDIA_CATEGORIES = (
        ("Events", "Events"),
        ("Classroom", "Classroom"),
        ("Activities", "Activities"),
        ("Campus", "Campus"),
        ("Banner", "Banner"),
    )

    section = models.ForeignKey(
        GallerySection,
        on_delete=models.CASCADE,
        related_name="items",
        null=True,
        blank=True,
        help_text="Gallery heading / album this item belongs to",
    )
    title = models.CharField(max_length=200)
    caption = models.CharField(max_length=255, blank=True)
    author = models.CharField(max_length=200, blank=True, null=True)
    location = models.CharField(max_length=200, blank=True, null=True)
    file = models.FileField(upload_to="gallery/", blank=True)
    embed_url = models.URLField(
        max_length=1024,
        blank=True,
        help_text="YouTube, MediaDelivery, or iframe embed URL (no file upload needed)",
    )
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES, default="image")
    category = models.CharField(max_length=20, choices=MEDIA_CATEGORIES, default="Events")
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["order", "-created_at"]
