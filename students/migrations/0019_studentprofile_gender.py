from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0018_alter_studentprofile_batch_num"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentprofile",
            name="gender",
            field=models.CharField(
                blank=True,
                choices=[("M", "Male"), ("F", "Female")],
                default="",
                help_text="M = Male, F = Female",
                max_length=1,
            ),
        ),
    ]
