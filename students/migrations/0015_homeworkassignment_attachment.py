from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0014_studenttransportassignment_drop_latitude_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="homeworkassignment",
            name="attachment",
            field=models.FileField(blank=True, null=True, upload_to="students/homework/"),
        ),
        migrations.AddField(
            model_name="homeworkassignment",
            name="attachment_kind",
            field=models.CharField(blank=True, choices=[("IMAGE", "Image"), ("PDF", "PDF")], default="", max_length=10),
        ),
        migrations.AddField(
            model_name="homeworkassignment",
            name="attachment_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]

