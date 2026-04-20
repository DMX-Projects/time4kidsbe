from django.db import models
from django.utils import timezone

from franchises.models import Franchise, ParentProfile


class StudentProfile(models.Model):
    """Student profile linked to parent"""
    parent = models.ForeignKey(ParentProfile, on_delete=models.CASCADE, related_name="students")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    class_name = models.CharField(max_length=50, help_text="e.g., KG-2 Section A")
    roll_number = models.CharField(max_length=50, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    admission_date = models.DateField(null=True, blank=True)
    profile_picture = models.ImageField(upload_to="students/profiles/", null=True, blank=True)
    is_active = models.BooleanField(default=True)
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
    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE, related_name="portal_announcements")
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    published_at = models.DateTimeField(default=timezone.now)
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
    title = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
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


class SupportTicket(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        CLOSED = "CLOSED", "Closed"

    parent = models.ForeignKey(ParentProfile, on_delete=models.CASCADE, related_name="support_tickets")
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    franchise_reply = models.TextField(blank=True)
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


class TransportRoute(models.Model):
    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE, related_name="transport_routes")
    route_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    map_url = models.URLField(blank=True, max_length=500)
    tracking_note = models.CharField(
        max_length=500,
        blank=True,
        help_text="Transport desk / GPS notice — live tracking is optional",
    )
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

