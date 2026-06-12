from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0015_parentdocument_contact_us"),
    ]

    operations = [
        migrations.AddField(
            model_name="parentdocument",
            name="source_path",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Stable checklist row key for admin CMS matching (e.g. checklist-row/audio-rhymes-pg-nursery-block-1).",
                max_length=512,
            ),
        ),
    ]
