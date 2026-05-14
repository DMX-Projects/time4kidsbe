"""Resync PostgreSQL sequence for accounts.User primary key."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = (
        "Fix duplicate-key on User.id when creating users (sequence behind MAX(id)). "
        "Run once after data import or manual SQL inserts."
    )

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            self.stderr.write(self.style.ERROR("This command only supports PostgreSQL."))
            return

        User = get_user_model()
        table = User._meta.db_table
        pk = User._meta.pk.column
        if not str(table).replace("_", "").isalnum() or not str(pk).replace("_", "").isalnum():
            self.stderr.write(self.style.ERROR("Refusing unsafe table/column names."))
            return

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT pg_get_serial_sequence(%s, %s)
                """,
                [table, pk],
            )
            row = cursor.fetchone()
            seq = row[0] if row else None

            if not seq:
                self.stderr.write(
                    self.style.ERROR(
                        f"No serial sequence for {table}.{pk} (identity column?). "
                        "Ask a DBA to advance the identity manually."
                    )
                )
                return

            cursor.execute(
                f"""
                SELECT COALESCE(MAX({connection.ops.quote_name(pk)}), 0)
                FROM {connection.ops.quote_name(table)}
                """
            )
            max_id = cursor.fetchone()[0]

            cursor.execute(
                "SELECT setval(%s, %s, true)",
                [seq, max_id],
            )
            new_val = cursor.fetchone()[0]

        self.stdout.write(
            self.style.SUCCESS(
                f"Sequence {seq} set from table {table}; MAX({pk})={max_id}, setval returned {new_val}. "
                "You can run createsuperuser again."
            )
        )
