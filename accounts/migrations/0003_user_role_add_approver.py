from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_user_username"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("ADMIN", "Admin"),
                    ("APPROVER", "Approver"),
                    ("FRANCHISE", "Franchise"),
                    ("PARENT", "Parent"),
                ],
                max_length=20,
            ),
        ),
    ]
