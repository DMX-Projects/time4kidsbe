from django.db import models

from franchises.models import Franchise


class DocumentCategory(models.TextChoices):
    AUDIO_RHYMES = "AUDIO_RHYMES", "Audio Rhymes"
    VIDEOS = "VIDEOS", "Watch • Hear • Learn"
    NEWSLETTERS = "NEWSLETTERS", "Newsletters"
    STUDENTS_KIT = "STUDENTS_KIT", "Students Kit"
    PARENTING_TIPS = "PARENTING_TIPS", "Parenting Tips & Articles"
    HOLIDAY_LISTS = "HOLIDAY_LISTS", "Holiday Lists"
    PRESCHOOL_POLICIES = "PRESCHOOL_POLICIES", "Preschool Policies (PDF)"
    CLASS_TIMETABLE = "CLASS_TIMETABLE", "Newsletter"


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
    file = models.FileField(upload_to="parent_documents/", blank=True, help_text="Upload document, audio, or video file")
    thumbnail = models.ImageField(upload_to="parent_documents/thumbnails/", null=True, blank=True)
    # Holiday-specific fields (only used when category is HOLIDAY_LISTS)
    state = models.CharField(max_length=2, choices=State.choices, null=True, blank=True, help_text="Required for Holiday Lists")
    academic_year = models.CharField(max_length=20, blank=True, help_text="e.g., AY 2025-26 (Required for Holiday Lists)")
    holiday_entries = models.JSONField(
        default=list,
        blank=True,
        help_text="Manual holiday rows: city, name, date (HOLIDAY_LISTS only).",
    )
    period_start = models.DateField(
        null=True,
        blank=True,
        help_text="Newsletter academic block start date",
    )
    period_end = models.DateField(
        null=True,
        blank=True,
        help_text="Newsletter academic block end date",
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = "Parent Document"
        verbose_name_plural = "Parent Documents"

    def __str__(self) -> str:
        franchise_name = "Global"
        if self.franchise_id:
            try:
                franchise_name = self.franchise.name
            except Franchise.DoesNotExist:
                franchise_name = f"(missing franchise #{self.franchise_id})"
        title = (self.title or "").strip() or "(no title)"
        return f"{self.get_category_display()} - {title} ({franchise_name})"


class FranchiseDocumentCategory(models.TextChoices):
    SOP = "SOP", "Standard Operating Procedures (SOP)"
    INFRASTRUCTURE_MANUAL = "INFRASTRUCTURE_MANUAL", "Infrastructure Manual & Purchase List"
    FORMATS = "FORMATS", "Formats"
    LEASE_AGREEMENT_DOCUMENTS = "LEASE_AGREEMENT_DOCUMENTS", "Lease Agreement Documents"
    INDENT_DOCUMENTS = "INDENT_DOCUMENTS", "Indent Documents (Inside & Outside AP)"
    ORDERING_DOCUMENTS = "ORDERING_DOCUMENTS", "Ordering Documents (IK & SM)"
    STUDENT_TRANSFER_POLICY = "STUDENT_TRANSFER_POLICY", "Student Transfer Policy"
    ACADEMIC_DOCUMENTS = "ACADEMIC_DOCUMENTS", "Academic Documents"
    REFRESHER_COURSE = "REFRESHER_COURSE", "Refresher Course"
    AKSHARABHYASAM_SUPPORT_SHEETS = "AKSHARABHYASAM_SUPPORT_SHEETS", "Aksharabhyasam Support Sheets"
    STUDENTS_KIT = "STUDENTS_KIT", "Students Kit"
    FRANCHISE_REFERRAL_INCENTIVES = "FRANCHISE_REFERRAL_INCENTIVES", "Franchise Referral Incentives"
    ROYALTY_PAYMENTS = "ROYALTY_PAYMENTS", "Royalty Payments"
    SOCIAL_MEDIA_SUPPORT = "SOCIAL_MEDIA_SUPPORT", "Social Media Uploads & Support Files"
    WELCOME_LETTERS = "WELCOME_LETTERS", "Welcome Letters"
    SUMMER_CAMP = "SUMMER_CAMP", "Summer Camp"
    HOLIDAY_LISTS = "HOLIDAY_LISTS", "Holiday Lists"
    WATCH_HEAR_LEARN = "WATCH_HEAR_LEARN", "Watch • Hear • Learn"
    ADMISSION_COUNSELLING = "ADMISSION_COUNSELLING", "Admission Counselling"
    ARTWORKS_MARKETING = "ARTWORKS_MARKETING", "Artworks & Marketing"
    CONCEPT_ROOM_DISPLAYS = "CONCEPT_ROOM_DISPLAYS", "Concept Room Pictures & Displays"
    REPORT_CARD_COMMENTS = "REPORT_CARD_COMMENTS", "Report Card Comments"
    PARENT_ORIENTATION = "PARENT_ORIENTATION", "Parents Orientation"
    COUNSELLING_TOOLS = "COUNSELLING_TOOLS", "Counselling Tools & Report Cards"
    PARENTING_TIPS = "PARENTING_TIPS", "Parenting Tips & Articles"


class FranchiseDocument(models.Model):
    """
    Resource Hub documents for franchise users.
    - If franchise is null, document is global (same for all centres).
    - If franchise is set, document is specific to that centre.
    """

    franchise = models.ForeignKey(
        Franchise,
        on_delete=models.CASCADE,
        related_name="franchise_documents",
        null=True,
        blank=True,
        help_text="Leave blank for global documents",
    )
    category = models.CharField(max_length=50, choices=FranchiseDocumentCategory.choices)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file = models.FileField(
        upload_to="franchise_documents/",
        blank=True,
        help_text="Upload document file (PDF/DOC/etc). Optional when embed_url is set.",
    )
    embed_url = models.URLField(
        max_length=1024,
        blank=True,
        help_text="YouTube, MediaDelivery, or other iframe embed URL (alternative to file upload).",
    )
    source_path = models.CharField(
        max_length=512,
        blank=True,
        null=True,
        unique=True,
        help_text="Legacy relative path under pc/ (e.g. holidayslist-2026-27/AP Holiday List.pdf) for Centre Page links.",
    )

    academic_year = models.CharField(max_length=20, blank=True, help_text="Optional academic year, if applicable.")

    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "-created_at"]
        verbose_name = "Franchise Resource Document"
        verbose_name_plural = "Franchise Resource Documents"

    def __str__(self) -> str:
        franchise_name = "Global"
        if self.franchise_id:
            try:
                franchise_name = self.franchise.name
            except Franchise.DoesNotExist:
                franchise_name = f"(missing franchise #{self.franchise_id})"
        title = (self.title or "").strip() or "(no title)"
        return f"{self.get_category_display()} - {title} ({franchise_name})"


class IndentRequest(models.Model):
    """
    Minimal workflow to support "Indents Placing" in the Franchise Resource Hub.
    A franchise user can submit an indent request; status can be updated by admin later.
    """

    REGION_CHOICES = (
        ("INSIDE_AP", "Inside AP"),
        ("OUTSIDE_AP", "Outside AP"),
    )

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    franchise = models.ForeignKey(
        Franchise,
        on_delete=models.CASCADE,
        related_name="indent_requests",
    )
    region = models.CharField(max_length=20, choices=REGION_CHOICES)
    academic_year = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    requested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self) -> str:
        try:
            franchise_label = self.franchise.name
        except Franchise.DoesNotExist:
            franchise_label = f"missing#{self.franchise_id}" if self.franchise_id else "none"
        return f"IndentRequest({franchise_label}) - {self.region} - {self.status}"

