from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("updates", "0004_socialmediaupload"),
    ]

    operations = [
        migrations.AddField(
            model_name="update",
            name="placement",
            field=models.CharField(
                choices=[
                    ("intro", "Intro board"),
                    ("franchise", "Franchise board"),
                ],
                default="franchise",
                max_length=20,
            ),
        ),
    ]
