from django.db import migrations, models
import django.db.models.deletion


def closed_to_resolved(apps, schema_editor):
    SupportTicket = apps.get_model("students", "SupportTicket")
    SupportTicket.objects.filter(status="CLOSED").update(status="RESOLVED")


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0022_announcement_email_dispatched_at"),
    ]

    operations = [
        migrations.RunPython(closed_to_resolved, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="supportticket",
            name="status",
            field=models.CharField(
                choices=[
                    ("OPEN", "Open"),
                    ("IN_PROGRESS", "In progress"),
                    ("RESOLVED", "Resolved"),
                ],
                default="OPEN",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="SupportTicketStatusEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "event_type",
                    models.CharField(
                        choices=[("STATUS_CHANGE", "Status change"), ("REPLY", "Franchise reply")],
                        max_length=20,
                    ),
                ),
                ("old_status", models.CharField(blank=True, max_length=20)),
                ("new_status", models.CharField(blank=True, max_length=20)),
                ("message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "ticket",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="status_events",
                        to="students.supportticket",
                    ),
                ),
            ],
            options={
                "verbose_name": "Support ticket status event",
                "verbose_name_plural": "Support ticket status events",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ParentPushDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.CharField(max_length=512)),
                ("platform", models.CharField(blank=True, max_length=20)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "parent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="push_devices",
                        to="franchises.parentprofile",
                    ),
                ),
            ],
            options={
                "verbose_name": "Parent push device",
                "verbose_name_plural": "Parent push devices",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="parentpushdevice",
            constraint=models.UniqueConstraint(fields=("parent", "token"), name="uniq_parent_push_token"),
        ),
    ]
