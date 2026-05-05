from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("franchises", "0014_alter_driverprofile_phone_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="franchise",
            name="school_program_cards",
            field=models.JSONField(blank=True, default=list),
        ),
    ]

