# Sync SupportTicket with live DB columns ho_reminder_message / ho_reminded_at.

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
                        UPDATE students_supportticket
                        SET ho_reminder_message = ''
                        WHERE ho_reminder_message IS NULL;
                        ALTER TABLE students_supportticket
                        ALTER COLUMN ho_reminder_message SET DEFAULT '';
                    """,
                    reverse_sql=migrations.RunSQL.noop,
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
