from django.db import models

from franchises.models import Franchise


class DocumentCategory(models.TextChoices):
    AUDIO_RHYMES = "AUDIO_RHYMES", "Audio Rhymes"
    VIDEOS = "VIDEOS", "Watch • Hear • Learn"
    NEWSLETTERS = "NEWSLETTERS", "Newsletters"
    STUDENTS_KIT = "STUDENTS_KIT", "Students Kit"
    PARENTING_TIPS = "PARENTING_TIPS", "Parenting Tips & Articles"
    HOLIDAY_LISTS = "HOLIDAY_LISTS", "Holiday Lists"


class ParentDocument(models.Model):
    """Documents accessible to parents - includes holiday lists"""
    class State(models.TextChoices):
        ANDHRA_PRADESH = "AP", "Andhra Pradesh"
        ARUNACHAL_PRADESH = "AR", "Arunachal Pradesh"
        ASSAM = "AS", "Assam"
        BIHAR = "BR", "Bihar"
        CHHATTISGARH = "CG", "Chhattisgarh"
        GOA = "GA", "Goa"
        GUJARAT = "GJ", "Gujarat"
        HARYANA = "HR", "Haryana"
        HIMACHAL_PRADESH = "HP", "Himachal Pradesh"
        JHARKHAND = "JH", "Jharkhand"
        KARNATAKA = "KA", "Karnataka"
        KERALA = "KL", "Kerala"
        MADHYA_PRADESH = "MP", "Madhya Pradesh"
        MAHARASHTRA = "MH", "Maharashtra"
        MANIPUR = "MN", "Manipur"
        MEGHALAYA = "ML", "Meghalaya"
        MIZORAM = "MZ", "Mizoram"
        NAGALAND = "NL", "Nagaland"
        ODISHA = "OD", "Odisha"
        PUNJAB = "PB", "Punjab"
        RAJASTHAN = "RJ", "Rajasthan"
        SIKKIM = "SK", "Sikkim"
        TAMIL_NADU = "TN", "Tamil Nadu"
        TELANGANA = "TS", "Telangana"
        TRIPURA = "TR", "Tripura"
        UTTAR_PRADESH = "UP", "Uttar Pradesh"
        UTTARAKHAND = "UK", "Uttarakhand"
        WEST_BENGAL = "WB", "West Bengal"
    
    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE, related_name="parent_documents", null=True, blank=True, help_text="Leave blank for global documents")
    category = models.CharField(max_length=50, choices=DocumentCategory.choices)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="parent_documents/", help_text="Upload document, audio, or video file")
    thumbnail = models.ImageField(upload_to="parent_documents/thumbnails/", null=True, blank=True)
    # Holiday-specific fields (only used when category is HOLIDAY_LISTS)
    state = models.CharField(max_length=2, choices=State.choices, null=True, blank=True, help_text="Required for Holiday Lists")
    academic_year = models.CharField(max_length=20, blank=True, help_text="e.g., AY 2025-26 (Required for Holiday Lists)")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = "Parent Document"
        verbose_name_plural = "Parent Documents"

    def __str__(self):
        franchise_name = self.franchise.name if self.franchise else "Global"
        return f"{self.get_category_display()} - {self.title} ({franchise_name})"

