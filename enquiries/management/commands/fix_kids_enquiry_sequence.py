"""Reset ``kids_enquiry_id_seq`` so the next INSERT gets id > MAX(id)."""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Fix kids_enquiry primary key sequence after manual imports or legacy data."

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("SELECT COALESCE(MAX(id), 0) FROM kids_enquiry")
            max_id = cursor.fetchone()[0]

            cursor.execute(
                "SELECT setval("
                "pg_get_serial_sequence('kids_enquiry', 'id'), "
                "%s, "
                "true"
                ")",
                [max_id],
            )
            cursor.execute(
                "SELECT currval(pg_get_serial_sequence('kids_enquiry', 'id'))"
            )
            curr = cursor.fetchone()[0]

        self.stdout.write(
            self.style.SUCCESS(
                f"kids_enquiry sequence reset: MAX(id)={max_id}, next id will be {curr + 1}."
            )
        )
