# Rename email -> "Emailid" (quoted) for legacy MySQL compatibility; state-only swap on Django side.

from django.db import migrations, models


RENAME_EMAIL_SQL = """
DO $emailid$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = current_schema() AND table_name = 'franchises_parentprofile' AND column_name = 'email'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = current_schema() AND table_name = 'franchises_parentprofile' AND column_name = 'Emailid'
  ) THEN
    ALTER TABLE franchises_parentprofile RENAME COLUMN email TO "Emailid";
  ELSIF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = current_schema() AND table_name = 'franchises_parentprofile' AND column_name = 'Emailid'
  ) THEN
    ALTER TABLE franchises_parentprofile ADD COLUMN "Emailid" varchar(254) NULL;
  END IF;
END $emailid$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("franchises", "0017_legacy_mysql_fields"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name="parentprofile", name="email"),
                migrations.AddField(
                    model_name="parentprofile",
                    name="Emailid",
                    field=models.EmailField(blank=True, db_column="Emailid", null=True),
                ),
            ],
            database_operations=[
                migrations.RunSQL(RENAME_EMAIL_SQL, migrations.RunSQL.noop),
            ],
        ),
    ]
