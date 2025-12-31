from django.db import models

class HeroSlide(models.Model):
    image = models.ImageField(upload_to='hero_slides/')
    mobile_image = models.ImageField(upload_to='hero_slides/mobile/', blank=True, null=True)
    alt_text = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return f"Hero Slide {self.id} - {self.alt_text}"
