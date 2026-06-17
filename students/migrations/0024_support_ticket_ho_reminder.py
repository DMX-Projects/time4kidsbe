from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0023_support_ticket_notifications"),
    ]

    operations = [
        migrations.AddField(
            model_name="supportticket",
            name="ho_reminder_message",
            field=models.TextField(
                blank=True,
                help_text="Head office reminder shown to the centre until the ticket is resolved.",
            ),
        ),
        migrations.AddField(
            model_name="supportticket",
            name="ho_reminded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
