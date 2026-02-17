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
