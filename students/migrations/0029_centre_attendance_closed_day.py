from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("franchises", "0013_alter_franchise_latitude_alter_franchise_longitude"),
        ("students", "0028_supportticket_ho_reminder_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="CentreAttendanceClosedDay",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("label", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "franchise",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attendance_closed_days",
                        to="franchises.franchise",
                    ),
                ),
            ],
            options={
                "verbose_name": "Centre attendance closed day",
                "verbose_name_plural": "Centre attendance closed days",
                "ordering": ["-date"],
            },
        ),
        migrations.AddConstraint(
            model_name="centreattendanceclosedday",
            constraint=models.UniqueConstraint(
                fields=("franchise", "date"),
                name="uniq_centre_attendance_closed_date",
            ),
        ),
    ]
