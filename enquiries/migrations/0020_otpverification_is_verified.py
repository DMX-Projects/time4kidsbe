# Generated manually for OTP verified flag

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enquiries", "0019_alter_crmlead_status_alter_franchiseenquiry_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="otpverification",
            name="is_verified",
            field=models.BooleanField(default=False),
        ),
    ]
