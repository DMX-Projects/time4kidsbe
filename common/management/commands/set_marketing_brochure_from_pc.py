"""
Point a marketing brochure at a file under PC_DOCUMENTS_ROOT (served as /media/pc/<path>).

Place your PDF in the pc folder, e.g.:
  C:\\Users\\Admin1\\Desktop\\pc\\admission-brochure\\admission-brochure.pdf

Then:
  python manage.py set_marketing_brochure_from_pc --slug admission-brochure
  python manage.py set_marketing_brochure_from_pc --slug admission-brochure --pc-path admission-brochure/admission-brochure.pdf
"""

import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from common.models import MarketingAsset

DEFAULT_PC_PATHS = {
    "admission-brochure": os.getenv(
        "ADMISSION_BROCHURE_PC_PATH",
        "admission-brochure/admission-brochure.pdf",
    ),
    "franchise-brochure": os.getenv(
        "FRANCHISE_BROCHURE_PC_PATH",
        "franchise-brochure/franchise-brochure.pdf",
    ),
}


class Command(BaseCommand):
    help = "Use a PDF from PC_DOCUMENTS_ROOT for a marketing asset (/media/pc/...)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug",
            required=True,
            choices=["admission-brochure", "franchise-brochure"],
        )
        parser.add_argument(
            "--pc-path",
            default="",
            help="Path under pc folder, e.g. admission-brochure/admission-brochure.pdf",
        )
        parser.add_argument("--title", default="", help="Display title (optional)")

    def handle(self, *args, **options):
        slug = options["slug"]
        pc_path = (options["pc_path"] or "").strip() or DEFAULT_PC_PATHS.get(slug, "")
        if not pc_path:
            raise CommandError(f"No --pc-path and no default for slug={slug!r}")

        root = getattr(settings, "PC_DOCUMENTS_ROOT", None)
        if not root or not Path(root).is_dir():
            raise CommandError(
                "PC_DOCUMENTS_ROOT is not set or folder missing. "
                'Set in .env, e.g. PC_DOCUMENTS_ROOT=C:\\Users\\Admin1\\Desktop\\pc'
            )

        rel = pc_path.replace("\\", "/").strip("/")
        disk = (Path(root) / rel).resolve()
        if not disk.is_file():
            raise CommandError(f"File not found under pc folder: {disk}")

        media_link = f"/media/pc/{rel}"
        title = (options["title"] or "").strip() or slug.replace("-", " ").title()

        asset, created = MarketingAsset.objects.get_or_create(
            slug=slug,
            defaults={"title": title, "is_active": True},
        )
        if asset.file:
            asset.file.delete(save=False)
        asset.file = None
        asset.title = title
        asset.link = media_link
        asset.is_active = True
        asset.save()

        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{action} {slug} -> {media_link}"))
        self.stdout.write(f"  Source: {disk}")
        self.stdout.write("  On production, set PC_DOCUMENTS_ROOT to the same pc folder on the server.")
