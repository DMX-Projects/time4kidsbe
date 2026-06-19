"""0026 was recorded as applied before these columns existed in the database."""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0028_rename_students_fr_franchi_6e2a0d_idx_students_fr_franchi_4b1e00_idx_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE students_announcement
                    ADD COLUMN IF NOT EXISTS ho_admin_id BIGINT NULL
                        REFERENCES users(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;
                ALTER TABLE students_announcement
                    ADD COLUMN IF NOT EXISTS publish_scope VARCHAR(32) NOT NULL DEFAULT '';
                ALTER TABLE students_announcement
                    ADD COLUMN IF NOT EXISTS target_states JSONB NOT NULL DEFAULT '[]';
                ALTER TABLE students_announcement
                    ADD COLUMN IF NOT EXISTS target_cities JSONB NOT NULL DEFAULT '[]';
                ALTER TABLE students_announcement
                    ADD COLUMN IF NOT EXISTS target_franchise_ids JSONB NOT NULL DEFAULT '[]';
                ALTER TABLE students_announcement
                    ADD COLUMN IF NOT EXISTS visible_to_centres BOOLEAN NOT NULL DEFAULT TRUE;
                ALTER TABLE students_announcement
                    ADD COLUMN IF NOT EXISTS visible_to_parents BOOLEAN NOT NULL DEFAULT TRUE;
                ALTER TABLE students_announcement
                    ALTER COLUMN franchise_id DROP NOT NULL;
                CREATE INDEX IF NOT EXISTS students_announcement_ho_admin_id_idx
                    ON students_announcement (ho_admin_id);
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
