# Renames snake_case columns to legacy quoted identifiers; adds Mobileno if missing.

from django.db import migrations, models


STUDENT_LEGACY_RENAME_SQL = """
DO $st$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'state')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'State') THEN
    ALTER TABLE students_studentprofile RENAME COLUMN state TO "State";
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'city')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'City') THEN
    ALTER TABLE students_studentprofile RENAME COLUMN city TO "City";
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'centre_name')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'Centre') THEN
    ALTER TABLE students_studentprofile RENAME COLUMN centre_name TO "Centre";
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'student_code')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'Idcardno') THEN
    ALTER TABLE students_studentprofile RENAME COLUMN student_code TO "Idcardno";
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'legacy_password')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'Password') THEN
    ALTER TABLE students_studentprofile RENAME COLUMN legacy_password TO "Password";
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'parent_name')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'ParentName') THEN
    ALTER TABLE students_studentprofile RENAME COLUMN parent_name TO "ParentName";
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'email')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'Emailid') THEN
    ALTER TABLE students_studentprofile RENAME COLUMN email TO "Emailid";
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'academic_year')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'Year') THEN
    ALTER TABLE students_studentprofile RENAME COLUMN academic_year TO "Year";
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'Mobileno') THEN
    ALTER TABLE students_studentprofile ADD COLUMN "Mobileno" varchar(255) NULL;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'State') THEN
    ALTER TABLE students_studentprofile ADD COLUMN "State" varchar(255) NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'City') THEN
    ALTER TABLE students_studentprofile ADD COLUMN "City" varchar(255) NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'Centre') THEN
    ALTER TABLE students_studentprofile ADD COLUMN "Centre" varchar(255) NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'Idcardno') THEN
    ALTER TABLE students_studentprofile ADD COLUMN "Idcardno" varchar(255) NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'Password') THEN
    ALTER TABLE students_studentprofile ADD COLUMN "Password" varchar(255) NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'ParentName') THEN
    ALTER TABLE students_studentprofile ADD COLUMN "ParentName" varchar(255) NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'Emailid') THEN
    ALTER TABLE students_studentprofile ADD COLUMN "Emailid" varchar(254) NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'students_studentprofile' AND column_name = 'Year') THEN
    ALTER TABLE students_studentprofile ADD COLUMN "Year" varchar(100) NULL;
  END IF;
END $st$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0016_legacy_mysql_fields"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name="studentprofile", name="state"),
                migrations.RemoveField(model_name="studentprofile", name="city"),
                migrations.RemoveField(model_name="studentprofile", name="centre_name"),
                migrations.RemoveField(model_name="studentprofile", name="student_code"),
                migrations.RemoveField(model_name="studentprofile", name="legacy_password"),
                migrations.RemoveField(model_name="studentprofile", name="parent_name"),
                migrations.RemoveField(model_name="studentprofile", name="email"),
                migrations.RemoveField(model_name="studentprofile", name="academic_year"),
                migrations.AddField(
                    model_name="studentprofile",
                    name="State",
                    field=models.CharField(blank=True, db_column="State", max_length=255, null=True),
                ),
                migrations.AddField(
                    model_name="studentprofile",
                    name="City",
                    field=models.CharField(blank=True, db_column="City", max_length=255, null=True),
                ),
                migrations.AddField(
                    model_name="studentprofile",
                    name="Centre",
                    field=models.CharField(blank=True, db_column="Centre", max_length=255, null=True),
                ),
                migrations.AddField(
                    model_name="studentprofile",
                    name="Idcardno",
                    field=models.CharField(blank=True, db_column="Idcardno", max_length=255, null=True),
                ),
                migrations.AddField(
                    model_name="studentprofile",
                    name="Password",
                    field=models.CharField(blank=True, db_column="Password", max_length=255, null=True),
                ),
                migrations.AddField(
                    model_name="studentprofile",
                    name="ParentName",
                    field=models.CharField(blank=True, db_column="ParentName", max_length=255, null=True),
                ),
                migrations.AddField(
                    model_name="studentprofile",
                    name="Emailid",
                    field=models.EmailField(blank=True, db_column="Emailid", null=True),
                ),
                migrations.AddField(
                    model_name="studentprofile",
                    name="Mobileno",
                    field=models.CharField(blank=True, db_column="Mobileno", max_length=255, null=True),
                ),
                migrations.AddField(
                    model_name="studentprofile",
                    name="Year",
                    field=models.CharField(blank=True, db_column="Year", max_length=100, null=True),
                ),
            ],
            database_operations=[
                migrations.RunSQL(STUDENT_LEGACY_RENAME_SQL, migrations.RunSQL.noop),
            ],
        ),
    ]
