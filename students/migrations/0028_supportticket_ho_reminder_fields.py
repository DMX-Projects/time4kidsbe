# SupportTicket HO reminder fields — idempotent on Postgres (add if missing).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0027_feerecord_source_line_serial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE students_supportticket
                            ADD COLUMN IF NOT EXISTS ho_reminder_message TEXT NOT NULL DEFAULT '';
                        ALTER TABLE students_supportticket
                            ADD COLUMN IF NOT EXISTS ho_reminded_at TIMESTAMPTZ NULL;
                    """,
                    reverse_sql="""
                        ALTER TABLE students_supportticket
                            DROP COLUMN IF EXISTS ho_reminded_at;
                        ALTER TABLE students_supportticket
                            DROP COLUMN IF EXISTS ho_reminder_message;
                    """,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="supportticket",
                    name="ho_reminder_message",
                    field=models.TextField(
                        blank=True,
                        default="",
                        help_text="Optional head-office note shown to the centre when reminding them to action this ticket.",
                    ),
                ),
                migrations.AddField(
                    model_name="supportticket",
                    name="ho_reminded_at",
                    field=models.DateTimeField(
                        blank=True,
                        help_text="When head office last reminded the centre about this ticket.",
                        null=True,
                    ),
                ),
            ],
        ),
    ]
