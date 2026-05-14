# Align users table with legacy MySQL names: drop legacy_* or rename into target if missing.

from django.db import migrations, models


USERS_LEGACY_SQL = """
DO $u$
BEGIN
  -- code
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'legacy_code') THEN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'code') THEN
      ALTER TABLE users RENAME COLUMN legacy_code TO code;
    ELSE
      ALTER TABLE users DROP COLUMN legacy_code;
    END IF;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'legacy_active') THEN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'active') THEN
      ALTER TABLE users RENAME COLUMN legacy_active TO active;
    ELSE
      ALTER TABLE users DROP COLUMN legacy_active;
    END IF;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'legacy_last_session') THEN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'last_session') THEN
      ALTER TABLE users RENAME COLUMN legacy_last_session TO last_session;
    ELSE
      ALTER TABLE users DROP COLUMN legacy_last_session;
    END IF;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'legacy_blocked') THEN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'blocked') THEN
      ALTER TABLE users RENAME COLUMN legacy_blocked TO blocked;
    ELSE
      ALTER TABLE users DROP COLUMN legacy_blocked;
    END IF;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'legacy_tries') THEN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'tries') THEN
      ALTER TABLE users RENAME COLUMN legacy_tries TO tries;
    ELSE
      ALTER TABLE users DROP COLUMN legacy_tries;
    END IF;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'legacy_last_try') THEN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'last_try') THEN
      ALTER TABLE users RENAME COLUMN legacy_last_try TO last_try;
    ELSE
      ALTER TABLE users DROP COLUMN legacy_last_try;
    END IF;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'legacy_mask_id') THEN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'mask_id') THEN
      ALTER TABLE users RENAME COLUMN legacy_mask_id TO mask_id;
    ELSE
      ALTER TABLE users DROP COLUMN legacy_mask_id;
    END IF;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'legacy_group_id') THEN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'group_id') THEN
      ALTER TABLE users RENAME COLUMN legacy_group_id TO group_id;
    ELSE
      ALTER TABLE users DROP COLUMN legacy_group_id;
    END IF;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'legacy_activation_time') THEN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'activation_time') THEN
      ALTER TABLE users RENAME COLUMN legacy_activation_time TO activation_time;
    ELSE
      ALTER TABLE users DROP COLUMN legacy_activation_time;
    END IF;
  END IF;

  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'legacy_last_action') THEN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'last_action') THEN
      ALTER TABLE users RENAME COLUMN legacy_last_action TO last_action;
    ELSE
      ALTER TABLE users DROP COLUMN legacy_last_action;
    END IF;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'code') THEN
    ALTER TABLE users ADD COLUMN code varchar(255) NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'active') THEN
    ALTER TABLE users ADD COLUMN active varchar(10) NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'last_session') THEN
    ALTER TABLE users ADD COLUMN last_session varchar(255) NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'blocked') THEN
    ALTER TABLE users ADD COLUMN blocked varchar(10) NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'tries') THEN
    ALTER TABLE users ADD COLUMN tries integer NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'last_try') THEN
    ALTER TABLE users ADD COLUMN last_try bigint NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'mask_id') THEN
    ALTER TABLE users ADD COLUMN mask_id integer NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'group_id') THEN
    ALTER TABLE users ADD COLUMN group_id integer NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'activation_time') THEN
    ALTER TABLE users ADD COLUMN activation_time bigint NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
             AND table_name = 'users' AND column_name = 'last_action') THEN
    ALTER TABLE users ADD COLUMN last_action bigint NULL;
  END IF;
END $u$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_legacy_mysql_fields"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name="user", name="legacy_code"),
                migrations.RemoveField(model_name="user", name="legacy_active"),
                migrations.RemoveField(model_name="user", name="legacy_last_session"),
                migrations.RemoveField(model_name="user", name="legacy_blocked"),
                migrations.RemoveField(model_name="user", name="legacy_tries"),
                migrations.RemoveField(model_name="user", name="legacy_last_try"),
                migrations.RemoveField(model_name="user", name="legacy_mask_id"),
                migrations.RemoveField(model_name="user", name="legacy_group_id"),
                migrations.RemoveField(model_name="user", name="legacy_activation_time"),
                migrations.RemoveField(model_name="user", name="legacy_last_action"),
                migrations.AddField(
                    model_name="user",
                    name="code",
                    field=models.CharField(blank=True, max_length=255, null=True),
                ),
                migrations.AddField(
                    model_name="user",
                    name="active",
                    field=models.CharField(blank=True, max_length=10, null=True),
                ),
                migrations.AddField(
                    model_name="user",
                    name="last_session",
                    field=models.CharField(blank=True, max_length=255, null=True),
                ),
                migrations.AddField(
                    model_name="user",
                    name="blocked",
                    field=models.CharField(blank=True, max_length=10, null=True),
                ),
                migrations.AddField(
                    model_name="user",
                    name="tries",
                    field=models.IntegerField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="user",
                    name="last_try",
                    field=models.BigIntegerField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="user",
                    name="mask_id",
                    field=models.IntegerField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="user",
                    name="group_id",
                    field=models.IntegerField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="user",
                    name="activation_time",
                    field=models.BigIntegerField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="user",
                    name="last_action",
                    field=models.BigIntegerField(blank=True, null=True),
                ),
            ],
            database_operations=[
                migrations.RunSQL(USERS_LEGACY_SQL, migrations.RunSQL.noop),
            ],
        ),
    ]
