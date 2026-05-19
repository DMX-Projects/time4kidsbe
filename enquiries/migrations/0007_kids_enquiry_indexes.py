from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enquiries", "0006_kidsenquiry"),
    ]

    state_operations = [
        migrations.AddIndex(
            model_name="kidsenquiry",
            index=models.Index(fields=["created_date"], name="idx_kids_enquiry_created_date"),
        ),
        migrations.AddIndex(
            model_name="kidsenquiry",
            index=models.Index(
                fields=["mobileno", "enquiry_type"],
                name="idx_kids_enquiry_mobile_type",
            ),
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=state_operations,
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "CREATE INDEX IF NOT EXISTS idx_kids_enquiry_created_date "
                        "ON kids_enquiry (created_date);"
                    ),
                    reverse_sql="DROP INDEX IF EXISTS idx_kids_enquiry_created_date;",
                ),
                migrations.RunSQL(
                    sql=(
                        "CREATE INDEX IF NOT EXISTS idx_kids_enquiry_mobile_type "
                        "ON kids_enquiry (mobileno, enquiry_type);"
                    ),
                    reverse_sql="DROP INDEX IF EXISTS idx_kids_enquiry_mobile_type;",
                ),
            ],
        ),
    ]
