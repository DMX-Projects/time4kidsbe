"""
One command to sync filesystem assets into PostgreSQL (FranchiseDocument + files in media/).

  python manage.py sync_all_content_to_database
"""

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from documents.models import FranchiseDocument


class Command(BaseCommand):
    help = "Import pc/ PDFs and public franchise images into the database."

    def add_arguments(self, parser):
        parser.add_argument("--skip-pc", action="store_true")
        parser.add_argument("--skip-public", action="store_true")

    def handle(self, *args, **options):
        if not options["skip_pc"]:
            root = getattr(settings, "PC_DOCUMENTS_ROOT", None)
            if not root:
                raise CommandError("PC_DOCUMENTS_ROOT is not set.")
            self.stdout.write("Importing pc/ folder into FranchiseDocument…")
            call_command("import_pc_documents", root=str(root), update=True)

        if not options["skip_public"]:
            self.stdout.write("Importing time4kids/public franchise images into FranchiseDocument…")
            call_command("import_franchise_public_assets", update=True)

        total = FranchiseDocument.objects.count()
        self.stdout.write(self.style.SUCCESS(f"Database sync complete. FranchiseDocument rows: {total}"))
