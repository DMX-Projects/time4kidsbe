from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0009_parentdocument_period_dates"),
    ]

    operations = [
        migrations.AddField(
            model_name="parentdocument",
            name="holiday_entries",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Manual holiday rows: city, name, date (HOLIDAY_LISTS only).",
            ),
        ),
        migrations.AlterField(
            model_name="parentdocument",
            name="file",
            field=models.FileField(
                blank=True,
                help_text="Upload document, audio, or video file",
                upload_to="parent_documents/",
            ),
        ),
    ]
