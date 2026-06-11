from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0021_announcement_targeting"),
    ]

    operations = [
        migrations.AddField(
            model_name="announcement",
            name="email_dispatched_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Set when parent notification emails have been sent for this announcement.",
                null=True,
            ),
        ),
    ]
