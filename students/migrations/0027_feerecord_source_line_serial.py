from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0026_announcement_drop_spurious_columns"),
    ]

    operations = [
        migrations.AddField(
            model_name="feerecord",
            name="line_serial",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="feerecord",
            name="source",
            field=models.CharField(
                choices=[("MANUAL", "Manual"), ("TIKES", "TiKES")],
                default="MANUAL",
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="feerecord",
            constraint=models.UniqueConstraint(
                condition=models.Q(("source", "TIKES")),
                fields=("student", "line_serial"),
                name="students_feerecord_unique_tikes_line",
            ),
        ),
    ]
