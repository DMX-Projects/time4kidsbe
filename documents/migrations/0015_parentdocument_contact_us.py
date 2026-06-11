from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0014_audio_rhymes_ay_2026_27_label"),
    ]

    operations = [
        migrations.AlterField(
            model_name="parentdocument",
            name="category",
            field=models.CharField(
                choices=[
                    ("AUDIO_RHYMES", "Audio Rhymes (AY 2026-27)"),
                    ("VIDEOS", "Watch Hear and Learn (AY 2026-27)"),
                    ("NEWSLETTERS", "Newsletters"),
                    ("STUDENTS_KIT", "Students Kit AY 2026-27"),
                    ("CONTACT_US", "Contact Us"),
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
