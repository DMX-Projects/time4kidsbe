from django.db import models


class HeroSlide(models.Model):
    image = models.ImageField(upload_to='hero_slides/')
    mobile_image = models.ImageField(upload_to='hero_slides/mobile/', blank=True, null=True)
    alt_text = models.CharField(max_length=255, blank=True)
    link = models.CharField(max_length=500, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return f"Hero Slide {self.id} - {self.alt_text}"


class Holiday(models.Model):
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


    state = models.CharField(max_length=2, choices=State.choices)
    academic_year = models.CharField(max_length=20, help_text="e.g., AY 2025-26")
    document = models.FileField(upload_to='holidays/', help_text="Upload holiday list document (PDF)")
    title = models.CharField(max_length=255, blank=True, help_text="Optional: Custom title (defaults to state name)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['state', '-academic_year']
        verbose_name = "Holiday List"
        verbose_name_plural = "Holiday Lists"

    def __str__(self):
        title = self.title or self.get_state_display()
        return f"{title} ({self.academic_year})"
