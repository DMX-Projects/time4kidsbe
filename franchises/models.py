from django.conf import settings
from django.db import models
from django.utils.text import slugify

from accounts.models import User, UserRole


class FranchiseLocation(models.Model):
    """Model to store available franchise center locations."""
    
    # Indian states choices
    STATE_CHOICES = [
        ('AN', 'Andaman and Nicobar Islands'),
        ('AP', 'Andhra Pradesh'),
        ('AR', 'Arunachal Pradesh'),
        ('AS', 'Assam'),
        ('BR', 'Bihar'),
        ('CH', 'Chandigarh'),
        ('CT', 'Chhattisgarh'),
        ('DN', 'Dadra and Nagar Haveli'),
        ('DD', 'Daman and Diu'),
        ('DL', 'Delhi'),
        ('GA', 'Goa'),
        ('GJ', 'Gujarat'),
        ('HR', 'Haryana'),
        ('HP', 'Himachal Pradesh'),
        ('JK', 'Jammu and Kashmir'),
        ('JH', 'Jharkhand'),
        ('KA', 'Karnataka'),
        ('KL', 'Kerala'),
        ('LA', 'Ladakh'),
        ('LD', 'Lakshadweep'),
        ('MP', 'Madhya Pradesh'),
        ('MH', 'Maharashtra'),
        ('MN', 'Manipur'),
        ('ML', 'Meghalaya'),
        ('MZ', 'Mizoram'),
        ('NL', 'Nagaland'),
        ('OR', 'Odisha'),
        ('PY', 'Puducherry'),
        ('PB', 'Punjab'),
        ('RJ', 'Rajasthan'),
        ('SK', 'Sikkim'),
        ('TN', 'Tamil Nadu'),
        ('TG', 'Telangana'),
        ('TR', 'Tripura'),
        ('UP', 'Uttar Pradesh'),
        ('UT', 'Uttarakhand'),
        ('WB', 'West Bengal'),
    ]
    
    city_name = models.CharField(max_length=100, unique=True, help_text="Name of the city")
    state = models.CharField(max_length=2, choices=STATE_CHOICES, help_text="State where the city is located")
    is_active = models.BooleanField(default=True, help_text="Display this location on the website")
    display_order = models.IntegerField(default=0, help_text="Order to display (lower numbers first)")
    
    # Landmark Fields for "Our Presence" Ladder
    landmark_name = models.CharField(max_length=150, blank=True, default='', help_text="Name of the landmark (e.g., Charminar)")
    LANDMARK_TYPE_CHOICES = [
        ('backwaters', 'Backwaters'),
        ('fort_generic', 'Fort (Generic)'),
        ('temple_bengal', 'Temple (Bengal Style)'),
        ('vidhana_soudha', 'Vidhana Soudha'),
        ('carpet', 'Carpet/Textile'),
        ('marine_drive', 'Marine Drive'),
        ('bandel_church', 'Bandel Church'),
        ('howrah_bridge', 'Howrah Bridge'),
        ('charminar', 'Charminar'),
        ('arch_dam', 'Arch Dam'),
        ('fort_water', 'Water Fort'),
        ('temple_gopuram', 'Temple Gopuram'),
        ('lake_generic', 'Lake (Generic)'),
        ('beach_generic', 'Beach (Generic)'),
        ('bara_imambara', 'Bara Imambara'),
        ('hill_park', 'Hill Park'),
        ('gateway_of_india', 'Gateway of India'),
        ('rockfort', 'Rockfort'),
        ('golghar', 'Golghar'),
        ('shaniwar_wada', 'Shaniwar Wada'),
        ('waterfall', 'Waterfall'),
        ('temple_kalinga', 'Temple (Kalinga Style)'),
        ('temple_kerala', 'Temple (Kerala Style)'),
        ('temple_padmanabhaswamy', 'Padmanabhaswamy Temple'),
        ('cactus_garden', 'Cactus Garden'),
        ('beach_rk', 'RK Beach'),
        ('temple_hill', 'Hill Temple'),
        ('fort_moat', 'Fort Moat'),
    ]
    landmark_type = models.CharField(
        max_length=50, 
        choices=LANDMARK_TYPE_CHOICES, 
        default='fort_generic',
        help_text="Type of landmark icon to display"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'city_name']
        verbose_name = "Franchise Location"
        verbose_name_plural = "Franchise Locations"

    def __str__(self):
        return f"{self.city_name}, {self.get_state_display()}"


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
    
    # Enhanced Fields
    google_map_link = models.URLField(blank=True, max_length=500)
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    
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


class FranchiseHeroSlide(models.Model):
    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE, related_name="hero_slides")
    image = models.ImageField(upload_to="franchises/hero_slides/")
    alt_text = models.CharField(max_length=255, blank=True)
    link = models.URLField(blank=True)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "-created_at"]
        verbose_name = "Franchise Hero Slide"
        verbose_name_plural = "Franchise Hero Slides"

    def __str__(self):
        return f"{self.franchise.name} - Slide {self.order}"


class FranchiseGalleryItem(models.Model):
    MEDIA_TYPE_CHOICES = [
        ('photo', 'Photo'),
        ('video', 'Video'),
    ]

    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE, related_name="gallery_items")
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default='photo')
    title = models.CharField(max_length=255)
    image = models.ImageField(upload_to="franchises/gallery/", help_text="Photo or Video Thumbnail")
    video_link = models.URLField(blank=True, help_text="YouTube/Vimeo link for videos")
    academic_year = models.CharField(max_length=20, default="2023-24", help_text="e.g. 2023-24")
    event_category = models.CharField(max_length=100, default="General", help_text="e.g. Annual Day")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Franchise Gallery Item"
        verbose_name_plural = "Franchise Gallery Items"

    def __str__(self):
        return f"{self.franchise.name} - {self.title} ({self.media_type})"
