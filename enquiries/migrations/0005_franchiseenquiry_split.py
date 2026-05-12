# Generated manually: split franchise leads into `franchise_enquiry` table.

from django.core.validators import RegexValidator
from django.db import migrations, models
import django.db.models.deletion


def migrate_franchise_enquiries(apps, schema_editor):
    Enquiry = apps.get_model("enquiries", "Enquiry")
    FranchiseEnquiry = apps.get_model("enquiries", "FranchiseEnquiry")
    to_move = list(Enquiry.objects.filter(enquiry_type="FRANCHISE"))
    for e in to_move:
        FranchiseEnquiry.objects.create(
            name=e.name,
            email=e.email,
            phone=e.phone or "",
            message=e.message or "",
            franchise_id=e.franchise_id,
            city=e.city or "",
            status=e.status or "new",
            created_at=e.created_at,
        )
    Enquiry.objects.filter(enquiry_type="FRANCHISE").delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("franchises", "0016_alter_franchise_table_alter_franchiselocation_table"),
        ("enquiries", "0004_alter_enquiry_table"),
    ]

    operations = [
        migrations.CreateModel(
            name="FranchiseEnquiry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("email", models.EmailField(max_length=254)),
                (
                    "phone",
                    models.CharField(
                        blank=True,
                        max_length=10,
                        validators=[RegexValidator(r"^\d{10}$", "Phone number must be exactly 10 digits.")],
                    ),
                ),
                ("message", models.TextField(blank=True)),
                (
                    "city",
                    models.CharField(blank=True, max_length=100),
                ),
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
                        related_name="franchise_enquiries",
                        to="franchises.franchise",
                    ),
                ),
            ],
            options={
                "db_table": "franchise_enquiry",
                "ordering": ["-created_at"],
            },
        ),
        migrations.RunPython(migrate_franchise_enquiries, noop_reverse),
        migrations.AlterField(
            model_name="enquiry",
            name="enquiry_type",
            field=models.CharField(
                choices=[("ADMISSION", "Admission"), ("CONTACT", "Contact")],
                max_length=20,
            ),
        ),
    ]
