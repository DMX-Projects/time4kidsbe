from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("gallery", "0004_mediaitem_author_mediaitem_location"),
    ]

    operations = [
        migrations.CreateModel(
            name="GallerySection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("slug", models.SlugField(blank=True, max_length=220)),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Gallery heading",
                "verbose_name_plural": "Gallery headings",
                "ordering": ["order", "title"],
            },
        ),
        migrations.AddField(
            model_name="mediaitem",
            name="caption",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="mediaitem",
            name="embed_url",
            field=models.URLField(
                blank=True,
                help_text="YouTube, MediaDelivery, or iframe embed URL (no file upload needed)",
                max_length=1024,
            ),
        ),
        migrations.AddField(
            model_name="mediaitem",
            name="order",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="mediaitem",
            name="section",
            field=models.ForeignKey(
                blank=True,
                help_text="Gallery heading / album this item belongs to",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="items",
                to="gallery.gallerysection",
            ),
        ),
        migrations.AlterField(
            model_name="mediaitem",
            name="file",
            field=models.FileField(blank=True, upload_to="gallery/"),
        ),
        migrations.AlterField(
            model_name="mediaitem",
            name="media_type",
            field=models.CharField(
                choices=[("image", "Image"), ("video", "Video"), ("embed", "Embed (iframe)")],
                default="image",
                max_length=10,
            ),
        ),
    ]
