import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator

from franchises.models import DriverProfile, Franchise, ParentProfile


class StudentProfile(models.Model):
    """Student profile linked to parent"""

    class Gender(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"

    parent = models.ForeignKey(ParentProfile, on_delete=models.CASCADE, related_name="students")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    class_name = models.CharField(max_length=50, help_text="e.g., KG-2")
    section = models.CharField(max_length=50, blank=True, default="")
    gender = models.CharField(
        max_length=1,
        choices=Gender.choices,
        blank=True,
        default="",
        help_text="M = Male, F = Female",
    )
    roll_number = models.CharField(max_length=50, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    admission_date = models.DateField(null=True, blank=True)
    profile_picture = models.ImageField(upload_to="students/profiles/", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    blood_group = models.CharField(max_length=10, blank=True, default="")
    emergency_contact = models.CharField(max_length=100, blank=True, default="")

    # Legacy MySQL column names (db_column preserves exact identifiers in PostgreSQL).
    State = models.CharField(max_length=255, blank=True, null=True, db_column="State")
    City = models.CharField(max_length=255, blank=True, null=True, db_column="City")
    Centre = models.CharField(max_length=255, blank=True, null=True, db_column="Centre")
    Idcardno = models.CharField(max_length=255, blank=True, null=True, db_column="Idcardno")
    Password = models.CharField(max_length=255, blank=True, null=True, db_column="Password")
    batch_num = models.CharField(max_length=50, blank=True, null=True, db_column="batch_num")
    ParentName = models.CharField(max_length=255, blank=True, null=True, db_column="ParentName")
    Emailid = models.EmailField(blank=True, null=True, db_column="Emailid")
    Mobileno = models.CharField(max_length=255, blank=True, null=True, db_column="Mobileno")
    Year = models.CharField(max_length=100, blank=True, null=True, db_column="Year")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["first_name", "last_name"]
        verbose_name = "Student Profile"
        verbose_name_plural = "Student Profiles"

    def __str__(self) -> str:
        name = f"{(self.first_name or '').strip()} {(self.last_name or '').strip()}".strip() or "(no name)"
        cn = (self.class_name or "").strip() or "(class)"
        return f"{name} ({cn})"

    @property
    def full_name(self) -> str:
        return f"{(self.first_name or '').strip()} {(self.last_name or '').strip()}".strip() or "(no name)"


class Grade(models.Model):
    """Student grades/marks"""
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="grades")
    subject = models.CharField(max_length=100)
    exam_type = models.CharField(max_length=50, help_text="e.g., Mid-term, Final, Quiz")
    marks_obtained = models.DecimalField(max_digits=5, decimal_places=2)
    total_marks = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    grade = models.CharField(max_length=10, blank=True, help_text="e.g., A+, A, B+")
    exam_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-exam_date", "subject"]
        verbose_name = "Grade"
        verbose_name_plural = "Grades"

    def __str__(self) -> str:
        if not self.student_id:
            who = "(no student)"
        else:
            try:
                who = self.student.full_name
            except StudentProfile.DoesNotExist:
                who = f"missing student #{self.student_id}"
        subj = (self.subject or "").strip() or "(subject)"
        exam = (self.exam_type or "").strip() or "(exam type)"
        return f"{who} - {subj} ({exam})"

    @property
    def percentage(self):
        if self.total_marks > 0:
            return round((self.marks_obtained / self.total_marks) * 100, 2)
        return 0


class StudentAchievement(models.Model):
    """Milestones published by a centre; optionally scoped to one child or centre-wide."""

    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE, related_name="student_achievements")
    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="achievements",
        help_text="Leave empty to show to all families at this centre.",
    )
    title = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    achieved_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-achieved_date", "-created_at"]
        verbose_name = "Student achievement"
        verbose_name_plural = "Student achievements"

    def __str__(self) -> str:
        t = (self.title or "").strip() or "(untitled)"
        if not self.student_id:
            who = "Centre-wide"
        else:
            try:
                who = self.student.full_name
            except StudentProfile.DoesNotExist:
                who = f"missing student #{self.student_id}"
        return f"{t} ({who})"


class HomeworkAssignment(models.Model):
    """Date-wise homework; optional per-student or per-class or whole centre."""

    class AttachmentKind(models.TextChoices):
        IMAGE = "IMAGE", "Image"
        PDF = "PDF", "PDF"

    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE, related_name="homework_assignments")
    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="homework_assignments",
    )
    class_name = models.CharField(
        max_length=120,
        blank=True,
        help_text="Must match StudentProfile.class_name when student is empty. Empty = all classes at centre.",
    )
    assigned_date = models.DateField()
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    attachment = models.FileField(upload_to="students/homework/", null=True, blank=True)
    attachment_name = models.CharField(max_length=255, blank=True, default="")
    attachment_kind = models.CharField(max_length=10, choices=AttachmentKind.choices, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-assigned_date", "-created_at"]
        verbose_name = "Homework assignment"
        verbose_name_plural = "Homework assignments"

    def __str__(self) -> str:
        t = (self.title or "").strip() or "(untitled)"
        return f"{t} ({self.assigned_date})"


class Announcement(models.Model):
    franchise = models.ForeignKey(
        Franchise,
        on_delete=models.CASCADE,
        related_name="portal_announcements",
        null=True,
        blank=True,
        help_text="Null for head-office global notifications with publish targeting.",
    )
    ho_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ho_announcements",
        help_text="Head office admin who published this global notification.",
    )
    publish_scope = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text="pan_india, state, city, franchises, or one_centre when franchise is null.",
    )
    target_states = models.JSONField(default=list, blank=True)
    target_cities = models.JSONField(default=list, blank=True)
    target_franchise_ids = models.JSONField(default=list, blank=True)
    visible_to_parents = models.BooleanField(
        default=True,
        help_text="When true, parents at matching centres see this in the parent app.",
    )
    visible_to_centres = models.BooleanField(
        default=True,
        help_text="When true, matching franchise centres see this in their notifications inbox.",
    )
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="announcements",
        help_text="When set, only this student's parent sees the notification.",
    )
    class_name = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="When student is empty, limits to parents with a child in this class. Empty = all parents.",
    )
    published_at = models.DateTimeField(default=timezone.now)
    email_dispatched_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set when parent notification emails have been sent for this announcement.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        verbose_name = "Announcement"
        verbose_name_plural = "Announcements"

    def __str__(self) -> str:
        t = (self.title or "").strip() or "(untitled)"
        if not self.franchise_id:
            return f"{t} (no franchise)"
        try:
            centre = self.franchise.name
        except Franchise.DoesNotExist:
            return f"{t} (missing franchise #{self.franchise_id})"
        return f"{t} ({centre})"


class AttendanceRecord(models.Model):
    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        ABSENT = "ABSENT", "Absent"
        LATE = "LATE", "Late"
        EXCUSED = "EXCUSED", "Excused"
        HOLIDAY = "HOLIDAY", "Holiday"

    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PRESENT)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "student_id"]
        verbose_name = "Attendance record"
        verbose_name_plural = "Attendance records"
        constraints = [
            models.UniqueConstraint(fields=["student", "date"], name="uniq_attendance_student_date"),
        ]

    def __str__(self) -> str:
        if not self.student_id:
            who = "(no student)"
        else:
            try:
                who = self.student.full_name
            except StudentProfile.DoesNotExist:
                who = f"missing student #{self.student_id}"
        return f"{who} - {self.date} ({self.get_status_display()})"


class FeeRecord(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        OVERDUE = "OVERDUE", "Overdue"

    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="fee_records")
    fee_structure_name = models.CharField(max_length=255, blank=True)
    id_card_no = models.CharField(max_length=100, blank=True)
    course = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    due_date = models.DateField()
    paid_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-due_date", "-created_at"]
        verbose_name = "Fee record"
        verbose_name_plural = "Fee records"

    def __str__(self) -> str:
        t = (self.title or "").strip() or "(untitled)"
        if not self.student_id:
            who = "(no student)"
        else:
            try:
                who = self.student.full_name
            except StudentProfile.DoesNotExist:
                who = f"missing student #{self.student_id}"
        return f"{t} - {who}"


class ParentFeePayment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        CANCELLED = "CANCELLED", "Cancelled"

    parent = models.ForeignKey(ParentProfile, on_delete=models.CASCADE, related_name="fee_payments")
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="fee_payments")
    fee_record = models.ForeignKey(
        FeeRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="parent_payments",
    )
    line_serial = models.PositiveIntegerField(default=0)
    fee_type = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    mode_of_payment = models.CharField(max_length=64, default="UPI QR")
    transaction_ref = models.CharField(max_length=64, blank=True, db_index=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Parent fee payment"
        verbose_name_plural = "Parent fee payments"

    def __str__(self) -> str:
        return f"{self.fee_type} ₹{self.amount} ({self.status})"


class SupportTicket(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        RESOLVED = "RESOLVED", "Resolved"

    parent = models.ForeignKey(ParentProfile, on_delete=models.CASCADE, related_name="support_tickets")
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    franchise_reply = models.TextField(blank=True)
    ho_reminder_message = models.TextField(
        blank=True,
        help_text="Head office reminder shown to the centre until the ticket is resolved.",
    )
    ho_reminded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Support ticket"
        verbose_name_plural = "Support tickets"

    def __str__(self) -> str:
        subj = (self.subject or "").strip() or "(no subject)"
        if not self.parent_id:
            parent_label = "(no parent)"
        else:
            try:
                parent_label = str(self.parent)
            except ParentProfile.DoesNotExist:
                parent_label = f"missing parent #{self.parent_id}"
        return f"{subj} ({parent_label})"


class SupportTicketStatusEvent(models.Model):
    """Audit trail for franchise ticket updates; drives parent in-app notifications."""

    class EventType(models.TextChoices):
        STATUS_CHANGE = "STATUS_CHANGE", "Status change"
        REPLY = "REPLY", "Franchise reply"

    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="status_events")
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Support ticket status event"
        verbose_name_plural = "Support ticket status events"

    def __str__(self) -> str:
        return f"ticket-{self.ticket_id}:{self.event_type}"


class ParentPushDevice(models.Model):
    """FCM device token registered by the parent mobile app."""

    parent = models.ForeignKey(ParentProfile, on_delete=models.CASCADE, related_name="push_devices")
    token = models.CharField(max_length=512)
    platform = models.CharField(max_length=20, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["parent", "token"], name="uniq_parent_push_token"),
        ]
        verbose_name = "Parent push device"
        verbose_name_plural = "Parent push devices"

    def __str__(self) -> str:
        return f"{self.parent_id}:{self.platform or 'device'}"


class FranchiseNotification(models.Model):
    """In-app alerts for franchise centres (head office reminders, etc.)."""

    class Source(models.TextChoices):
        SUPPORT_TICKET = "support_ticket", "Support ticket"
        HEAD_OFFICE = "head_office", "Head office"

    franchise = models.ForeignKey(
        "franchises.Franchise",
        on_delete=models.CASCADE,
        related_name="portal_notifications",
    )
    source = models.CharField(max_length=32, choices=Source.choices, default=Source.HEAD_OFFICE)
    source_id = models.PositiveIntegerField(null=True, blank=True)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    action_path = models.CharField(
        max_length=255,
        blank=True,
        help_text="Franchise dashboard path, e.g. /dashboard/franchise/parent-tickets/",
    )
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Franchise notification"
        verbose_name_plural = "Franchise notifications"
        indexes = [
            models.Index(fields=["franchise", "-created_at"]),
            models.Index(fields=["franchise", "source", "source_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.franchise_id}:{self.source}:{self.title[:40]}"


class TransportRoute(models.Model):
    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE, related_name="transport_routes")
    route_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    map_url = models.URLField(blank=True, max_length=500)
    vehicle_number = models.CharField(max_length=80, blank=True)
    driver_name = models.CharField(max_length=255, blank=True)
    driver_phone = models.CharField(
        max_length=10, 
        blank=True,
        validators=[RegexValidator(r'^\d{10}$', 'Phone number must be exactly 10 digits.')]
    )
    driver_profile = models.ForeignKey(
        DriverProfile, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="assigned_routes"
    )
    driver_token = models.UUIDField(default=uuid.uuid4, db_index=True, editable=False)
    tracking_note = models.CharField(
        max_length=500,
        blank=True,
        help_text="Transport desk / GPS notice — live tracking is optional",
    )
    destination = models.CharField(max_length=255, blank=True)
    destination_latitude = models.DecimalField(max_digits=22, decimal_places=16, null=True, blank=True)
    destination_longitude = models.DecimalField(max_digits=22, decimal_places=16, null=True, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "route_name"]
        verbose_name = "Transport route"
        verbose_name_plural = "Transport routes"

    def __str__(self) -> str:
        rn = (self.route_name or "").strip() or "(route)"
        if not self.franchise_id:
            centre = "(no franchise)"
        else:
            try:
                centre = self.franchise.name
            except Franchise.DoesNotExist:
                centre = f"missing franchise #{self.franchise_id}"
        return f"{rn} ({centre})"


class StudentTransportAssignment(models.Model):
    student = models.OneToOneField(StudentProfile, on_delete=models.CASCADE, related_name="transport_assignment")
    route = models.ForeignKey(TransportRoute, on_delete=models.CASCADE, related_name="student_assignments")
    pickup_stop = models.CharField(max_length=255, blank=True)
    pickup_latitude = models.DecimalField(max_digits=22, decimal_places=16, null=True, blank=True)
    pickup_longitude = models.DecimalField(max_digits=22, decimal_places=16, null=True, blank=True)
    drop_stop = models.CharField(max_length=255, blank=True)
    drop_latitude = models.DecimalField(max_digits=22, decimal_places=16, null=True, blank=True)
    drop_longitude = models.DecimalField(max_digits=22, decimal_places=16, null=True, blank=True)
    pickup_time = models.TimeField(null=True, blank=True)
    drop_time = models.TimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["route__sort_order", "student__first_name"]

    def __str__(self) -> str:
        try:
            student_label = self.student.full_name
        except StudentProfile.DoesNotExist:
            student_label = f"missing student #{self.student_id}"
        return f"{student_label} -> {self.route_id}"


class TransportTrip(models.Model):
    class TripType(models.TextChoices):
        PICKUP = "PICKUP", "Pickup"
        DROP = "DROP", "Drop"

    class Status(models.TextChoices):
        NOT_STARTED = "NOT_STARTED", "Not started"
        LIVE = "LIVE", "Live"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    route = models.ForeignKey(TransportRoute, on_delete=models.CASCADE, related_name="trips")
    trip_type = models.CharField(max_length=20, choices=TripType.choices, default=TripType.PICKUP)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_STARTED)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_gps_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.route_id} {self.trip_type} {self.status}"


class TransportTripLocation(models.Model):
    trip = models.ForeignKey(TransportTrip, on_delete=models.CASCADE, related_name="locations")
    latitude = models.DecimalField(max_digits=22, decimal_places=16)
    longitude = models.DecimalField(max_digits=22, decimal_places=16)
    speed = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self) -> str:
        return f"{self.trip_id}: {self.latitude}, {self.longitude}"


class StudentTripStatus(models.Model):
    class Status(models.TextChoices):
        WAITING = "WAITING", "Waiting"
        PICKED_UP = "PICKED_UP", "Picked up"
        DROPPED = "DROPPED", "Dropped"
        ABSENT = "ABSENT", "Absent"

    trip = models.ForeignKey(TransportTrip, on_delete=models.CASCADE, related_name="student_statuses")
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="trip_statuses")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.WAITING)
    note = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["trip", "student"], name="uniq_trip_student_status"),
        ]

    def __str__(self) -> str:
        return f"{self.trip_id}:{self.student_id}:{self.status}"


class ParentNotificationRead(models.Model):
    """Tracks which aggregated notifications were read by a parent."""

    parent = models.ForeignKey(ParentProfile, on_delete=models.CASCADE, related_name="read_notifications")
    notification_key = models.CharField(max_length=120)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-read_at"]
        constraints = [
            models.UniqueConstraint(fields=["parent", "notification_key"], name="uniq_parent_notification_key"),
        ]

    def __str__(self) -> str:
        return f"{self.parent_id}:{self.notification_key}"
