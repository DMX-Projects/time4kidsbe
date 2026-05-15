"""
Point a marketing asset at a static file served by the Next.js frontend (public/).

Use when the PDF is deployed with the site at /brochures/<name>.pdf instead of Django /media/.

Example (live DB):
  set PUBLIC_SITE_URL=https://www.timekidspreschools.in
  python manage.py set_marketing_brochure_public_link --slug admission-brochure
"""

import os

from django.core.management.base import BaseCommand, CommandError

from common.models import MarketingAsset


class Command(BaseCommand):
    help = "Use a /brochures/*.pdf public URL for a marketing asset (clears Django file field)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug",
            required=True,
            choices=["admission-brochure", "franchise-brochure"],
        )
        parser.add_argument(
            "--public-path",
            default="",
            help="Path on the site, e.g. /brochures/admission-brochure.pdf (default: /brochures/<slug>.pdf)",
        )
        parser.add_argument(
            "--site-url",
            default="",
            help="Public site origin (default: PUBLIC_SITE_URL env)",
        )

    def handle(self, *args, **options):
        slug = options["slug"]
        site = (options["site_url"] or os.getenv("PUBLIC_SITE_URL", "")).strip().rstrip("/")
        if not site:
            raise CommandError("Set --site-url or PUBLIC_SITE_URL (e.g. https://www.timekidspreschools.in)")

        public_path = (options["public_path"] or "").strip() or f"/brochures/{slug}.pdf"
        if not public_path.startswith("/"):
            public_path = f"/{public_path}"

        link = f"{site}{public_path}"

        try:
            asset = MarketingAsset.objects.get(slug=slug)
        except MarketingAsset.DoesNotExist:
            raise CommandError(f"No MarketingAsset with slug={slug!r}") from None

        if asset.file:
            asset.file.delete(save=False)
        asset.file = None
        asset.link = link
        asset.is_active = True
        asset.save(update_fields=["file", "link", "is_active", "updated_at"])

        self.stdout.write(self.style.SUCCESS(f"Updated {slug}"))
        self.stdout.write(f"  link: {link}")
        self.stdout.write("  Deploy the frontend so public/brochures/ is on the server.")
