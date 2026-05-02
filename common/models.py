import json

from django.db import models


class HomePageJSONField(models.JSONField):
    """
    Tolerate malformed or legacy JSON in `HomePageContent.data` so admin and ORM
    reads do not return 500 (PostgreSQL/SQLite can still store bad values if
    written outside Django).
    """

    def from_db_value(self, value, expression, connection):
        if value in (None, ""):
            return {}
        try:
            return super().from_db_value(value, expression, connection)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}


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


class HomeTestimonial(models.Model):
    """Parent quotes on the public home page (horizontal testimonial section)."""

    text = models.TextField()
    author = models.CharField(max_length=200)
    relation = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=200, blank=True)
    rating = models.PositiveSmallIntegerField(default=5)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Home testimonial"
        verbose_name_plural = "Home testimonials"

    def __str__(self) -> str:
        author = (self.author or "").strip() or "(no author)"
        raw = self.text
        body = raw if isinstance(raw, str) else ("" if raw is None else str(raw))
        snippet = (body[:40] + "...") if len(body) > 40 else body
        return f"{author}: {snippet}"


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


class HomePageContent(models.Model):
    """Singleton (use pk=1): JSON for marketing sections on the main homepage."""

    data = HomePageJSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Home page content"
        verbose_name_plural = "Home page content"

    def __str__(self) -> str:
        return f"Home page content (pk={self.pk})" if self.pk else "Home page content (new)"


class PageContent(models.Model):
    """Generic JSON for marketing sections on any page (admission, franchise, etc.)."""
    slug = models.SlugField(unique=True, help_text="Page identifier (e.g. 'admission', 'franchise-opportunity')")
    data = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Page content"
        verbose_name_plural = "Page contents"

    def __str__(self) -> str:
        return f"Page Content: {self.slug}"


class MarketingAsset(models.Model):
    """Assets like brochures, virtual tour links, etc. that can be downloaded or viewed."""
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, help_text="e.g. 'admission-brochure', 'franchise-brochure', 'virtual-tour'")
    file = models.FileField(upload_to='assets/', blank=True, null=True, help_text="Upload the file (PDF, etc.)")
    link = models.URLField(blank=True, max_length=500, help_text="Or provide a link (e.g. YouTube virtual tour)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Marketing asset"
        verbose_name_plural = "Marketing assets"

    def __str__(self):
        return f"{self.title} ({self.slug})"
