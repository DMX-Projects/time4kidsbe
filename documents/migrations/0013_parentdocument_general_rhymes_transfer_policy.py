from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0012_parentdocument_audio_file"),
    ]

    operations = [
        migrations.AlterField(
            model_name="parentdocument",
            name="category",
            field=models.CharField(
                choices=[
                    ("AUDIO_RHYMES", "Audio Rhymes (AY 2025-26)"),
                    ("VIDEOS", "Watch Hear and Learn (AY 2026-27)"),
                    ("NEWSLETTERS", "Newsletters"),
                    ("STUDENTS_KIT", "Students Kit AY 2026-27"),
                    ("GENERAL_RHYMES", "General Rhymes"),
                    ("STUDENT_TRANSFER_POLICY", "Student Transfer Policy"),
                    ("PARENTING_TIPS", "Parenting Tips & Articles"),
                    ("HOLIDAY_LISTS", "Holiday Lists"),
                    ("PRESCHOOL_POLICIES", "Preschool Policies (PDF)"),
                    ("CLASS_TIMETABLE", "Newsletter"),
                ],
                max_length=50,
            ),
        ),
    ]
