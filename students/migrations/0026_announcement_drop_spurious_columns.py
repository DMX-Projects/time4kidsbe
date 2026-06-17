# Remove campaign-only columns that were mistakenly added to students_announcement.
# Franchise centre notifications use Announcement rows without publish_scope targeting.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0025_supportticket_student"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE students_announcement DROP COLUMN IF EXISTS publish_scope;
                ALTER TABLE students_announcement DROP COLUMN IF EXISTS target_states;
                ALTER TABLE students_announcement DROP COLUMN IF EXISTS target_cities;
                ALTER TABLE students_announcement DROP COLUMN IF EXISTS target_franchise_ids;
                ALTER TABLE students_announcement DROP COLUMN IF EXISTS ho_admin_id;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
