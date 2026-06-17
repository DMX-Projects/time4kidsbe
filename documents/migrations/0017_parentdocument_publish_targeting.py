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
                        "ALTER TABLE documents_parentdocument "
                        "ADD COLUMN IF NOT EXISTS publish_scope varchar(20) NOT NULL DEFAULT 'pan_india';"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE documents_parentdocument "
                        "ADD COLUMN IF NOT EXISTS target_states jsonb NOT NULL DEFAULT '[]'::jsonb;"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE documents_parentdocument "
                        "ADD COLUMN IF NOT EXISTS target_cities jsonb NOT NULL DEFAULT '[]'::jsonb;"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE documents_parentdocument "
                        "ADD COLUMN IF NOT EXISTS target_franchise_ids jsonb NOT NULL DEFAULT '[]'::jsonb;"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE documents_parentdocument "
                        "ADD COLUMN IF NOT EXISTS target_class_names jsonb NOT NULL DEFAULT '[]'::jsonb;"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="parentdocument",
                    name="publish_scope",
                    field=models.CharField(
                        blank=True,
                        choices=[
                            ("pan_india", "Pan-India"),
                            ("state", "State"),
                            ("city", "City"),
                            ("franchises", "Multiple centres"),
                            ("one_centre", "One centre"),
                        ],
                        default="pan_india",
                        max_length=20,
                    ),
                ),
                migrations.AddField(
                    model_name="parentdocument",
                    name="target_states",
                    field=models.JSONField(blank=True, default=list),
                ),
                migrations.AddField(
                    model_name="parentdocument",
                    name="target_cities",
                    field=models.JSONField(blank=True, default=list),
                ),
                migrations.AddField(
                    model_name="parentdocument",
                    name="target_franchise_ids",
                    field=models.JSONField(blank=True, default=list),
                ),
                migrations.AddField(
                    model_name="parentdocument",
                    name="target_class_names",
                    field=models.JSONField(blank=True, default=list),
                ),
            ],
        ),
    ]
