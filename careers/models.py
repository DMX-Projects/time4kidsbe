from django.conf import settings
from django.db import models


class Career(models.Model):
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="careers")
    title = models.CharField(max_length=255)
    department = models.CharField(max_length=100, default="General")
    type = models.CharField(max_length=50, default="Full-time")
    description = models.TextField()
    location = models.CharField(max_length=255, blank=True)
    apply_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class JobApplication(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewed', 'Reviewed'),
        ('shortlisted', 'Shortlisted'),
        ('rejected', 'Rejected'),
    ]

    career = models.ForeignKey(Career, on_delete=models.CASCADE, related_name="applications")
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    linkedin_url = models.URLField(max_length=500, blank=True)
    resume = models.FileField(upload_to='resumes/')
    cover_letter = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-applied_at"]

    def __str__(self) -> str:
        return f"{self.full_name} - {self.career.title}"
