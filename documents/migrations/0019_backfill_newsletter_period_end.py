"""Backfill period_end for newsletters that only have period_start set."""

from django.db import migrations


def backfill_period_end(apps, schema_editor):
    ParentDocument = apps.get_model("documents", "ParentDocument")
    qs = ParentDocument.objects.filter(
        category="CLASS_TIMETABLE",
        period_start__isnull=False,
        period_end__isnull=True,
    )
    for doc in qs.iterator():
        doc.period_end = doc.period_start
        doc.save(update_fields=["period_end"])


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0018_drop_spurious_video_file_column"),
    ]

    operations = [
        migrations.RunPython(backfill_period_end, migrations.RunPython.noop),
    ]
