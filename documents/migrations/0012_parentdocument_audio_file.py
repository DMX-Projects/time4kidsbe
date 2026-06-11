from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0011_parentdocument_newsletter_embed_urls"),
    ]

    operations = [
        migrations.AddField(
            model_name="parentdocument",
            name="audio_file",
            field=models.FileField(
                blank=True,
                help_text="Optional newsletter audio upload (MP3, WAV, etc.).",
                upload_to="parent_documents/newsletter_audio/",
            ),
        ),
        migrations.AlterField(
            model_name="parentdocument",
            name="audio_embed_url",
            field=models.URLField(
                blank=True,
                help_text="Legacy newsletter audio embed iframe URL.",
                max_length=1024,
            ),
        ),
    ]
