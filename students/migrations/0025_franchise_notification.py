from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("franchises", "0013_alter_franchise_latitude_alter_franchise_longitude"),
        ("students", "0024_support_ticket_ho_reminder"),
    ]

    operations = [
        migrations.CreateModel(
            name="FranchiseNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "source",
                    models.CharField(
                        choices=[("support_ticket", "Support ticket"), ("head_office", "Head office")],
                        default="head_office",
                        max_length=32,
                    ),
                ),
                ("source_id", models.PositiveIntegerField(blank=True, null=True)),
                ("title", models.CharField(max_length=255)),
                ("body", models.TextField(blank=True)),
                (
                    "action_path",
                    models.CharField(
                        blank=True,
                        help_text="Franchise dashboard path, e.g. /dashboard/franchise/parent-tickets/",
                        max_length=255,
                    ),
                ),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "franchise",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="portal_notifications",
                        to="franchises.franchise",
                    ),
                ),
            ],
            options={
                "verbose_name": "Franchise notification",
                "verbose_name_plural": "Franchise notifications",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="franchisenotification",
            index=models.Index(fields=["franchise", "-created_at"], name="students_fr_franchi_6e2a0d_idx"),
        ),
        migrations.AddIndex(
            model_name="franchisenotification",
            index=models.Index(fields=["franchise", "source", "source_id"], name="students_fr_franchi_8c4f1a_idx"),
        ),
    ]
