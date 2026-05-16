from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0006_franchise_document_source_path_and_categories"),
    ]

    operations = [
        migrations.AddField(
            model_name="franchisedocument",
            name="embed_url",
            field=models.URLField(
                blank=True,
                help_text="YouTube, MediaDelivery, or other iframe embed URL (alternative to file upload).",
                max_length=1024,
            ),
        ),
        migrations.AlterField(
            model_name="franchisedocument",
            name="file",
            field=models.FileField(
                blank=True,
                help_text="Upload document file (PDF/DOC/etc). Optional when embed_url is set.",
                upload_to="franchise_documents/",
            ),
        ),
    ]
