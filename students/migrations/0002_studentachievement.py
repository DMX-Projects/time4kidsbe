import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("franchises", "0008_franchisegalleryitem"),
        ("students", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentAchievement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("notes", models.TextField(blank=True)),
                ("achieved_date", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "franchise",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_achievements",
                        to="franchises.franchise",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        blank=True,
                        help_text="Leave empty to show to all families at this centre.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="achievements",
                        to="students.studentprofile",
                    ),
                ),
            ],
            options={
                "verbose_name": "Student achievement",
                "verbose_name_plural": "Student achievements",
                "ordering": ["-achieved_date", "-created_at"],
            },
        ),
    ]
