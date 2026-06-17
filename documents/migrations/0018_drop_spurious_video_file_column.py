# Drop stray video_file column on documents_parentdocument (not in Django model).
# Inserts fail with: null value in column "video_file" violates not-null constraint

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0017_parentdocument_publish_targeting"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE documents_parentdocument DROP COLUMN IF EXISTS video_file;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
