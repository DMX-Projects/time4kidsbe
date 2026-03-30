from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("franchises", "0008_franchisegalleryitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="parentprofile",
            name="phone",
            field=models.CharField(blank=True, default="", max_length=30),
        ),
        migrations.AddField(
            model_name="parentprofile",
            name="address",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="parentprofile",
            name="city",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="parentprofile",
            name="photo_url",
            field=models.URLField(blank=True, default="", max_length=500),
        ),
    ]
