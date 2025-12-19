from django.conf import settings
from django.db import models
from django.utils.text import slugify

from accounts.models import User, UserRole


class Franchise(models.Model):
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="franchises")
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="franchise_profile")

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    about = models.TextField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    programs = models.TextField(blank=True)
    facilities = models.TextField(blank=True)
    hero_image = models.ImageField(upload_to="franchises/hero/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.admin.email})"


class ParentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="parent_profile")
    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE, related_name="parents")
    child_name = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["user__full_name"]
        verbose_name = "Parent"
        verbose_name_plural = "Parents"

    def __str__(self) -> str:
        return f"Parent {self.user.full_name} - {self.franchise.name}"

    @property
    def admin(self) -> User:
        return self.franchise.admin
