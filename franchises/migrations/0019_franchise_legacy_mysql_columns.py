# Legacy MySQL columns on franchise; uses IF NOT EXISTS when columns already exist from imports.

from django.db import migrations, models


ADD_FRANCHISE_LEGACY_SQL = """
DO $fr$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
                 AND table_name = 'franchise' AND column_name = 'fname') THEN
    ALTER TABLE franchise ADD COLUMN fname varchar(255) NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
                 AND table_name = 'franchise' AND column_name = 'countryid') THEN
    ALTER TABLE franchise ADD COLUMN countryid integer NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
                 AND table_name = 'franchise' AND column_name = 'stateid') THEN
    ALTER TABLE franchise ADD COLUMN stateid integer NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
                 AND table_name = 'franchise' AND column_name = 'statename') THEN
    ALTER TABLE franchise ADD COLUMN statename varchar(255) NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
                 AND table_name = 'franchise' AND column_name = 'cityid') THEN
    ALTER TABLE franchise ADD COLUMN cityid integer NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
                 AND table_name = 'franchise' AND column_name = 'cityname') THEN
    ALTER TABLE franchise ADD COLUMN cityname varchar(255) NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
                 AND table_name = 'franchise' AND column_name = 'areaid') THEN
    ALTER TABLE franchise ADD COLUMN areaid integer NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
                 AND table_name = 'franchise' AND column_name = 'areaname') THEN
    ALTER TABLE franchise ADD COLUMN areaname varchar(255) NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
                 AND table_name = 'franchise' AND column_name = 'phoneno') THEN
    ALTER TABLE franchise ADD COLUMN phoneno varchar(255) NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
                 AND table_name = 'franchise' AND column_name = 'email') THEN
    ALTER TABLE franchise ADD COLUMN email varchar(254) NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema()
                 AND table_name = 'franchise' AND column_name = 'url') THEN
    ALTER TABLE franchise ADD COLUMN url varchar(500) NULL;
  END IF;
END $fr$;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("franchises", "0018_legacy_sql_column_names"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="franchise",
                    name="fname",
                    field=models.CharField(blank=True, max_length=255, null=True),
                ),
                migrations.AddField(
                    model_name="franchise",
                    name="countryid",
                    field=models.IntegerField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="franchise",
                    name="stateid",
                    field=models.IntegerField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="franchise",
                    name="statename",
                    field=models.CharField(blank=True, max_length=255, null=True),
                ),
                migrations.AddField(
                    model_name="franchise",
                    name="cityid",
                    field=models.IntegerField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="franchise",
                    name="cityname",
                    field=models.CharField(blank=True, max_length=255, null=True),
                ),
                migrations.AddField(
                    model_name="franchise",
                    name="areaid",
                    field=models.IntegerField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name="franchise",
                    name="areaname",
                    field=models.CharField(blank=True, max_length=255, null=True),
                ),
                migrations.AddField(
                    model_name="franchise",
                    name="phoneno",
                    field=models.CharField(blank=True, max_length=255, null=True),
                ),
                migrations.AddField(
                    model_name="franchise",
                    name="email",
                    field=models.EmailField(blank=True, max_length=254, null=True),
                ),
                migrations.AddField(
                    model_name="franchise",
                    name="url",
                    field=models.URLField(blank=True, max_length=500, null=True),
                ),
            ],
            database_operations=[
                migrations.RunSQL(ADD_FRANCHISE_LEGACY_SQL, migrations.RunSQL.noop),
            ],
        ),
    ]
