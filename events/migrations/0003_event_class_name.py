from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0002_alter_event_table"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="class_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Empty = all classes (public centre page + all parents). Set to limit parent app visibility.",
                max_length=120,
            ),
        ),
    ]
