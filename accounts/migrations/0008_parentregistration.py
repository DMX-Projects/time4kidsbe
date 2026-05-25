import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("franchises", "0019_franchise_legacy_mysql_columns"),
        ("accounts", "0007_legacy_sql_column_names"),
    ]

    operations = [
        migrations.CreateModel(
            name="ParentRegistration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("parent_name", models.CharField(max_length=255)),
                ("email", models.EmailField(max_length=254)),
                (
                    "phone",
                    models.CharField(
                        blank=True,
                        max_length=10,
                        validators=[
                            django.core.validators.RegexValidator(
                                "^\\d{10}$", "Phone number must be exactly 10 digits."
                            )
                        ],
                    ),
                ),
                ("child_name", models.CharField(blank=True, max_length=255)),
                ("child_age", models.CharField(blank=True, max_length=50)),
                ("program", models.CharField(blank=True, max_length=100)),
                ("city", models.CharField(blank=True, max_length=100)),
                ("message", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("new", "New"), ("in-progress", "In Progress"), ("closed", "Closed")],
                        default="new",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "franchise",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="parent_registrations",
                        to="franchises.franchise",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="registration_records",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Parent registration",
                "verbose_name_plural": "Parent registrations",
                "db_table": "parent_registration",
                "ordering": ["-created_at"],
            },
        ),
    ]
