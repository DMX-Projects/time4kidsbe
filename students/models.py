from django.db import models

from franchises.models import ParentProfile


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

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.class_name})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


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

    def __str__(self):
        return f"{self.student.full_name} - {self.subject} ({self.exam_type})"

    @property
    def percentage(self):
        if self.total_marks > 0:
            return round((self.marks_obtained / self.total_marks) * 100, 2)
        return 0

