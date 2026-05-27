from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("franchises", "0019_franchise_legacy_mysql_columns"),
    ]

    operations = [
        migrations.AddField(
            model_name="driverprofile",
            name="service_number",
            field=models.CharField(blank=True, help_text="Driver / vehicle service ID", max_length=50),
        ),
        migrations.AddField(
            model_name="driverprofile",
            name="license_document",
            field=models.FileField(blank=True, null=True, upload_to="drivers/licenses/"),
        ),
        migrations.AddField(
            model_name="driverprofile",
            name="vehicle_rc",
            field=models.FileField(blank=True, null=True, upload_to="drivers/vehicle_rc/"),
        ),
        migrations.AddField(
            model_name="driverprofile",
            name="vehicle_insurance",
            field=models.FileField(blank=True, null=True, upload_to="drivers/vehicle_insurance/"),
        ),
    ]
