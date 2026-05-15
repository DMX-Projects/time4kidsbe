"""
Upload or replace a marketing brochure PDF (admission / franchise / home download tile).

Examples:
  python manage.py upload_marketing_brochure --slug admission-brochure --file "C:\\Users\\Admin1\\Desktop\\admission.pdf" --title "Admission Brochure"
  python manage.py upload_marketing_brochure --slug franchise-brochure --file "C:\\Users\\Admin1\\Desktop\\franchise.pdf" --title "Franchise Brochure"

Production: uploading from your PC only updates the database path — copy the file to the
server MEDIA_ROOT/assets/ on the app host, OR deploy via Next public/ +:
  python manage.py set_marketing_brochure_public_link --slug admission-brochure --site-url https://your-domain.com
"""

from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from common.models import MarketingAsset


class Command(BaseCommand):
    help = "Upload a PDF to MarketingAsset (used on Admission / Franchise / Home brochure links)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug",
            required=True,
            choices=["admission-brochure", "franchise-brochure", "virtual-tour"],
            help="admission-brochure = Admission page | franchise-brochure = Franchise page + Home tile",
        )
        parser.add_argument("--file", required=True, help="Full path to your PDF file")
        parser.add_argument("--title", default="", help="Display title (optional)")

    def handle(self, *args, **options):
        slug = options["slug"]
        file_path = Path(options["file"]).expanduser().resolve()
        if not file_path.is_file():
            raise CommandError(f"File not found: {file_path}")
        if file_path.suffix.lower() != ".pdf":
            self.stdout.write(self.style.WARNING("Warning: file is not .pdf — continuing anyway."))

        title = (options["title"] or "").strip() or slug.replace("-", " ").title()

        asset, created = MarketingAsset.objects.get_or_create(
            slug=slug,
            defaults={"title": title, "is_active": True},
        )
        asset.title = title
        asset.is_active = True
        asset.link = ""

        with file_path.open("rb") as fh:
            asset.file.save(file_path.name, File(fh), save=False)
        asset.save()

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} MarketingAsset slug={slug} title={title}"))
        self.stdout.write(f"  Stored at: {asset.file.name}")
        self.stdout.write("  View on site after refresh:")
        if slug == "admission-brochure":
            self.stdout.write("    - /admission (Download Corner)")
        elif slug == "franchise-brochure":
            self.stdout.write("    - /franchise (Download Brochure section)")
            self.stdout.write("    - / (Home → Download Brochure tile)")
