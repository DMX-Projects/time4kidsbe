from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0010_parentdocument_holiday_entries"),
    ]

    operations = [
        migrations.AddField(
            model_name="parentdocument",
            name="audio_embed_url",
            field=models.URLField(
                blank=True,
                help_text="Optional newsletter audio embed iframe URL.",
                max_length=1024,
            ),
        ),
        migrations.AddField(
            model_name="parentdocument",
            name="video_embed_url",
            field=models.URLField(
                blank=True,
                help_text="Optional newsletter video embed (YouTube, Bunny iframe, etc.).",
                max_length=1024,
            ),
        ),
    ]
