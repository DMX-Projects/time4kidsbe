from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enquiries", "0023_assigned_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="crmlead",
            name="utm_content",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        migrations.AddField(
            model_name="crmlead",
            name="utm_term",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
    ]
