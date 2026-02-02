from django.db import models

class MediaItem(models.Model):
    MEDIA_TYPES = (
        ('image', 'Image'),
        ('video', 'Video'),
    )

    MEDIA_CATEGORIES = (
        ('Events', 'Events'),
        ('Classroom', 'Classroom'),
        ('Activities', 'Activities'),
        ('Campus', 'Campus'),
        ('Banner', 'Banner'),
    )

    title = models.CharField(max_length=200)
    author = models.CharField(max_length=200, blank=True, null=True)
    location = models.CharField(max_length=200, blank=True, null=True)
    file = models.FileField(upload_to='gallery/')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES, default='image')
    category = models.CharField(max_length=20, choices=MEDIA_CATEGORIES, default='Events')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']
