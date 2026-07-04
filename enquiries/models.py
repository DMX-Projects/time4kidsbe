from django.db import models
from django.core.validators import RegexValidator

from franchises.models import Franchise


class EnquiryType(models.TextChoices):
    ADMISSION = "ADMISSION", "Admission"
    CONTACT = "CONTACT", "Contact"


class Enquiry(models.Model):
    enquiry_type = models.CharField(max_length=20, choices=EnquiryType.choices)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(
        max_length=10, 
        blank=True,
        validators=[RegexValidator(r'^\d{10}$', 'Phone number must be exactly 10 digits.')]
    )
    message = models.TextField(blank=True)
    franchise = models.ForeignKey(Franchise, on_delete=models.SET_NULL, null=True, blank=True, related_name="enquiries")
    city = models.CharField(max_length=100, blank=True)
    child_age = models.CharField(max_length=50, blank=True)
    status = models.CharField(
        max_length=30,
        choices=[
            ("new", "New"),
            ("contacted", "Contacted"),
            ("called", "Called"),
            ("follow_up", "Follow Up"),
            ("interested", "Interested"),
            ("meeting_scheduled", "Meeting Scheduled"),
            ("dropped", "Dropped"),
            ("not_interested", "Not Interested"),
            ("converted", "Converted"),
            ("in-progress", "In Progress"),
            ("closed", "Closed"),
        ],
        default="new",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "enquiry"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.enquiry_type} from {self.name}"


class FranchiseEnquiry(models.Model):
    """Franchise opportunity leads (separate from admission/contact `Enquiry`)."""

    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(
        max_length=10,
        blank=True,
        validators=[RegexValidator(r"^\d{10}$", "Phone number must be exactly 10 digits.")],
    )
    message = models.TextField(blank=True)
    franchise = models.ForeignKey(
        Franchise,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="franchise_enquiries",
    )
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=30,
        choices=[
            ("new", "New"),
            ("contacted", "Contacted"),
            ("called", "Called"),
            ("follow_up", "Follow Up"),
            ("interested", "Interested"),
            ("meeting_scheduled", "Meeting Scheduled"),
            ("dropped", "Dropped"),
            ("not_interested", "Not Interested"),
            ("converted", "Converted"),
            ("in-progress", "In Progress"),
            ("closed", "Closed"),
        ],
        default="new",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "franchise_enquiry"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Franchise lead from {self.name}"


class KidsEnquiry(models.Model):
    """
    Landing-page leads — mirrors ``public.kids_enquiry`` exactly:
    id, name, mobile, mobileno, email, state, city, location, enquiry_type,
    created_date, source, centre_name, centre_phone, centre_email,
    email_status, whatsapp_status, raw_payload.
    """

    name = models.TextField()
    mobile = models.TextField(blank=True, null=True)
    mobileno = models.TextField()
    email = models.TextField(blank=True, null=True)
    state = models.TextField(blank=True, null=True)
    city = models.TextField(blank=True, null=True)
    location = models.TextField(blank=True, null=True)
    enquiry_type = models.TextField()
    created_date = models.DateTimeField(auto_now_add=True)
    source = models.TextField(blank=True, null=True)
    centre_name = models.TextField(blank=True, null=True)
    centre_phone = models.TextField(blank=True, null=True)
    centre_email = models.TextField(blank=True, null=True)
    email_status = models.TextField(blank=True, null=True)
    whatsapp_status = models.TextField(blank=True, null=True)
    raw_payload = models.JSONField(default=dict)

    class Meta:
        db_table = "kids_enquiry"
        ordering = ["-created_date"]
        indexes = [
            models.Index(fields=["created_date"], name="idx_kids_enquiry_created_date"),
            models.Index(
                fields=["mobileno", "enquiry_type"],
                name="idx_kids_enquiry_mobile_type",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.enquiry_type})"


class CrmLeadSource(models.TextChoices):
    WEB = "web", "Website"
    FB = "fb", "Facebook"
    INSTA = "insta", "Instagram"


class CrmLeadStatus(models.TextChoices):
    NEW = "new", "New"
    CONTACTED = "contacted", "Contacted"
    CALLED = "called", "Called"
    FOLLOW_UP = "follow_up", "Follow Up"
    INTERESTED = "interested", "Interested"
    MEETING_SCHEDULED = "meeting_scheduled", "Meeting Scheduled"
    CONVERTED = "converted", "Converted"
    DROPPED = "dropped", "Dropped"
    NOT_INTERESTED = "not_interested", "Not Interested"


class CrmLead(models.Model):
    """Separate CRM leads for /crm/web, /crm/fb, and /crm/insta."""

    full_name = models.CharField(max_length=255)
    mobile = models.CharField(max_length=20)
    email = models.EmailField(blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    preferred_centre_location = models.CharField(max_length=255, blank=True, default="")
    franchise_type = models.CharField(max_length=100, blank=True, default="")
    investment_range = models.CharField(max_length=100, blank=True, default="")
    expected_start_date = models.CharField(max_length=100, blank=True, default="")
    comments = models.TextField(blank=True, default="")
    source = models.CharField(max_length=20, choices=CrmLeadSource.choices, default=CrmLeadSource.WEB)
    landing_page_url = models.URLField(max_length=500, blank=True, default="")
    utm_source = models.CharField(max_length=150, blank=True, default="")
    utm_medium = models.CharField(max_length=150, blank=True, default="")
    utm_campaign = models.CharField(max_length=150, blank=True, default="")
    status = models.CharField(max_length=30, choices=CrmLeadStatus.choices, default=CrmLeadStatus.NEW)
    meeting_date = models.DateTimeField(null=True, blank=True)
    next_follow_up_date = models.DateTimeField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "crm_leads"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"], name="idx_crm_leads_created_at"),
            models.Index(fields=["source"], name="idx_crm_leads_source"),
            models.Index(fields=["status"], name="idx_crm_leads_status"),
            models.Index(fields=["mobile"], name="idx_crm_leads_mobile"),
        ]

    def __str__(self) -> str:
        return f"CRM lead from {self.full_name} ({self.source})"


class CrmLeadNote(models.Model):
    lead = models.ForeignKey(CrmLead, on_delete=models.CASCADE, related_name="notes")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "crm_lead_notes"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Note for CRM lead {self.lead_id}"


class OTPVerification(models.Model):
    phone = models.CharField(max_length=20, unique=True)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "otp_verification"

    def __str__(self) -> str:
        return f"OTP for {self.phone}: {self.code}"
