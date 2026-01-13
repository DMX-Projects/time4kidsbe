from django.db import models

from franchises.models import Franchise


class EnquiryType(models.TextChoices):
    ADMISSION = "ADMISSION", "Admission"
    FRANCHISE = "FRANCHISE", "Franchise Opportunity"
    CONTACT = "CONTACT", "Contact"


class Enquiry(models.Model):
    enquiry_type = models.CharField(max_length=20, choices=EnquiryType.choices)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    message = models.TextField(blank=True)
    franchise = models.ForeignKey(Franchise, on_delete=models.SET_NULL, null=True, blank=True, related_name="enquiries")
    city = models.CharField(max_length=100, blank=True)
    child_age = models.CharField(max_length=50, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[("new", "New"), ("in-progress", "In Progress"), ("closed", "Closed")],
        default="new",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.enquiry_type} from {self.name}"
