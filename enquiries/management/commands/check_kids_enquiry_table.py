"""Verify ``kids_enquiry`` exists and a test row can be inserted (then deleted)."""

from django.core.management.base import BaseCommand
from django.db import connection

from enquiries.models import KidsEnquiry

EXPECTED_COLUMNS = {
    "id",
    "name",
    "mobile",
    "mobileno",
    "email",
    "state",
    "city",
    "location",
    "enquiry_type",
    "created_date",
    "source",
    "centre_name",
    "centre_phone",
    "centre_email",
    "email_status",
    "whatsapp_status",
    "raw_payload",
}


class Command(BaseCommand):
    help = "Check public.kids_enquiry schema and test insert/delete."

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema IN ('public', current_schema())
                  AND table_name = 'kids_enquiry'
                ORDER BY ordinal_position
                """
            )
            rows = cursor.fetchall()

        if not rows:
            self.stderr.write(self.style.ERROR("Table kids_enquiry not found in this database."))
            self.stderr.write(f"Database: {connection.settings_dict.get('NAME')}")
            return

        found = {r[0] for r in rows}
        self.stdout.write(f"Database: {connection.settings_dict.get('NAME')}")
        self.stdout.write("Columns on kids_enquiry:")
        for name, dtype, nullable in rows:
            self.stdout.write(f"  - {name}: {dtype} (nullable={nullable})")

        missing = EXPECTED_COLUMNS - found
        extra = found - EXPECTED_COLUMNS
        if missing:
            self.stderr.write(self.style.ERROR(f"Missing columns: {sorted(missing)}"))
        if extra:
            self.stdout.write(self.style.WARNING(f"Extra columns (OK): {sorted(extra)}"))

        try:
            row = KidsEnquiry.objects.create(
                name="__diagnostic_test__",
                mobile="9999999999",
                mobileno="9999999999",
                email="test@example.com",
                city="Test",
                location="Test",
                enquiry_type="Admission Enquiry",
                source="diagnostic",
                raw_payload={"test": True},
            )
            row.delete()
            self.stdout.write(self.style.SUCCESS("Test insert + delete succeeded."))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Test insert failed: {type(exc).__name__}: {exc}"))
