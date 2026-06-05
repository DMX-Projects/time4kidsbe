from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0020_parent_fee_payment"),
    ]

    operations = [
        migrations.AddField(
            model_name="announcement",
            name="class_name",
            field=models.CharField(
                blank=True,
                default="",
                help_text="When student is empty, limits to parents with a child in this class. Empty = all parents.",
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name="announcement",
            name="student",
            field=models.ForeignKey(
                blank=True,
                help_text="When set, only this student's parent sees the notification.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="announcements",
                to="students.studentprofile",
            ),
        ),
    ]
