# Generated manually for head-office notification campaigns.

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("franchises", "0001_initial"),
        ("students", "0022_announcement_email_dispatched_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnnouncementCampaign",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("body", models.TextField(blank=True)),
                (
                    "publish_scope",
                    models.CharField(
                        choices=[
                            ("pan_india", "Pan-India"),
                            ("state", "State"),
                            ("city", "City"),
                            ("franchises", "Multiple centres"),
                            ("one_centre", "One centre"),
                        ],
                        default="pan_india",
                        max_length=20,
                    ),
                ),
                ("target_states", models.JSONField(blank=True, default=list)),
                ("target_cities", models.JSONField(blank=True, default=list)),
                ("target_franchise_ids", models.JSONField(blank=True, default=list)),
                (
                    "class_name",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="When student is empty, limits to parents with a child in this class. Empty = all parents.",
                        max_length=120,
                    ),
                ),
                ("visible_to_parents", models.BooleanField(default=True)),
                ("visible_to_centres", models.BooleanField(default=True)),
                ("published_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "franchise",
                    models.ForeignKey(
                        blank=True,
                        help_text="Primary centre when publish_scope is one_centre.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="announcement_campaigns",
                        to="franchises.franchise",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        blank=True,
                        help_text="When set with one_centre, only this student's parent sees the notification.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="announcement_campaigns",
                        to="students.studentprofile",
                    ),
                ),
            ],
            options={
                "verbose_name": "Announcement campaign",
                "verbose_name_plural": "Announcement campaigns",
                "ordering": ["-published_at", "-created_at"],
            },
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE students_announcement "
                        "ADD COLUMN IF NOT EXISTS campaign_id bigint NULL;"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE students_announcement "
                        "ADD COLUMN IF NOT EXISTS visible_to_parents boolean NOT NULL DEFAULT true;"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE students_announcement "
                        "ADD COLUMN IF NOT EXISTS visible_to_centres boolean NOT NULL DEFAULT true;"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="announcement",
                    name="campaign",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deliveries",
                        to="students.announcementcampaign",
                    ),
                ),
                migrations.AddField(
                    model_name="announcement",
                    name="visible_to_parents",
                    field=models.BooleanField(default=True),
                ),
                migrations.AddField(
                    model_name="announcement",
                    name="visible_to_centres",
                    field=models.BooleanField(default=True),
                ),
            ],
        ),
        migrations.RunSQL(
            sql=(
                "DO $$ BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = "
                "'students_announcement_campaign_id_fk_students_announcementcampaign') THEN "
                "ALTER TABLE students_announcement "
                "ADD CONSTRAINT students_announcement_campaign_id_fk_students_announcementcampaign "
                "FOREIGN KEY (campaign_id) REFERENCES students_announcementcampaign(id) "
                "ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED; "
                "END IF; END $$;"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
