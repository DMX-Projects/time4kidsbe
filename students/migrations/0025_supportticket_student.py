from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0024_franchise_notification_read"),
    ]

    operations = [
        migrations.AddField(
            model_name="supportticket",
            name="student",
            field=models.ForeignKey(
                blank=True,
                help_text="Optional — which child this ticket is about.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="support_tickets",
                to="students.studentprofile",
            ),
        ),
    ]
