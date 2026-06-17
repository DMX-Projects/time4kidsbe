from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0016_parentdocument_source_path"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "UPDATE documents_parentdocument SET video_file = '' "
                        "WHERE video_file IS NULL;"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE documents_parentdocument "
                        "ALTER COLUMN video_file SET DEFAULT '';"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="parentdocument",
                    name="video_file",
                    field=models.FileField(
                        blank=True,
                        help_text="Optional newsletter video upload (MP4, WebM, etc.).",
                        upload_to="parent_documents/newsletter_video/",
                    ),
                ),
            ],
        ),
    ]
