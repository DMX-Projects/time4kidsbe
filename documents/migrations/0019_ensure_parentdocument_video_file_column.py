"""0017 used SeparateDatabaseAndState and assumed video_file already existed in DB."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0018_parentdocument_publish_targeting"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "ALTER TABLE documents_parentdocument "
                "ADD COLUMN IF NOT EXISTS video_file VARCHAR(100) NOT NULL DEFAULT '';"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
