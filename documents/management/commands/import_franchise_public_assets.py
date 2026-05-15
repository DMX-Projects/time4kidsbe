"""
Import franchise marketing images from time4kids/public/ into FranchiseDocument (PostgreSQL).

Usage:
  python manage.py import_franchise_public_assets
  python manage.py import_franchise_public_assets --update
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from documents.models import FranchiseDocument, FranchiseDocumentCategory


# Centre Page artwork labels (must match franchise-center-page-nav.ts)
PUBLIC_ARTWORKS: list[tuple[str, str]] = [
    (
        "franchise-artworks/social-media-promotions-ay-2026-27/social-media-promotion-1.png",
        "Admissions Open — Limited Seats",
    ),
    (
        "franchise-artworks/social-media-promotions-ay-2026-27/social-media-promotion-2.png",
        "Dedicated Teaching Staff — Admissions AY 2026-27",
    ),
    (
        "franchise-artworks/social-media-promotions-ay-2026-27/social-media-promotion-3.png",
        "Where Learning Begins with Joy",
    ),
    (
        "franchise-artworks/social-media-promotions-ay-2026-27/social-media-promotion-4.png",
        "Admissions Open — Call / Visit Today",
    ),
    (
        "franchise-artworks/social-media-promotions-ay-2026-27/social-media-promotion-5.png",
        "Give Your Child the Right Start",
    ),
    (
        "franchise-artworks/social-media-promotions-ay-2026-27/social-media-promotion-6.png",
        "Care and Safety — Admissions AY 2026-27",
    ),
    (
        "franchise-artworks/social-media-promotions-ay-2026-27/social-media-promotion-7.png",
        "A Safe & Nurturing Start",
    ),
    (
        "franchise-artworks/social-media-promotions-ay-2026-27/social-media-promotion-8.png",
        "The Best Pre-school for Your Child",
    ),
]

PUBLIC_GALLERY: list[tuple[str, str]] = [
    ("franchise-gallery/franchise-nep-compliant.png", "NEP 2020 compliant — T.I.M.E. Kids"),
    ("franchise-gallery/franchise-brochure-cover.png", "Become a franchisee of T.I.M.E. Kids pre-schools"),
    ("franchise-gallery/franchise-video-poster.png", "T.I.M.E. Kids franchise advantage"),
    ("franchise-gallery/franchise-promo-1.png", "Start your own preschool with T.I.M.E. Kids"),
    ("franchise-gallery/franchise-promo-2.png", "Partner with India's trusted preschool network"),
    ("franchise-gallery/franchise-promo-3.png", "Franchise opportunity — T.I.M.E. Kids"),
    ("franchise-gallery/franchise-promo-4.png", "Start your preschool franchise today"),
    ("franchise-gallery/franchise-promo-5.png", "Preschool franchise with T.I.M.E. Kids"),
    ("franchise-gallery/franchise-promo-6.png", "Launch a preschool with T.I.M.E. Kids"),
    ("franchise-gallery/franchise-promo-7.png", "Franchise opportunity — invest in preschool"),
]


class Command(BaseCommand):
    help = "Import public/franchise-* images into FranchiseDocument (database)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--public-root",
            type=str,
            default="",
            help="Path to time4kids/public (default: <repo>/time4kids/public)",
        )
        parser.add_argument("--update", action="store_true", help="Replace file when source_path exists")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        public_root = options["public_root"].strip()
        if public_root:
            root = Path(public_root).resolve()
        else:
            root = (settings.BASE_DIR.parent / "time4kids" / "public").resolve()

        if not root.is_dir():
            raise CommandError(f"Public folder not found: {root}")

        do_update = options["update"]
        dry_run = options["dry_run"]
        entries = [*PUBLIC_ARTWORKS, *PUBLIC_GALLERY]
        created = updated = skipped = missing = 0

        for rel, title in entries:
            path = root / rel.replace("/", "\\") if "\\" in str(root) else root / rel
            if not path.is_file():
                missing += 1
                self.stdout.write(self.style.WARNING(f"Missing: {rel}"))
                continue

            source_path = rel.replace("\\", "/")
            existing = FranchiseDocument.objects.filter(source_path=source_path).first()

            if existing and not do_update:
                skipped += 1
                continue

            if dry_run:
                action = "UPDATE" if existing else "CREATE"
                self.stdout.write(f"[dry-run] {action} {source_path} | {title}")
                continue

            with transaction.atomic():
                if existing:
                    doc = existing
                    doc.title = title
                    doc.category = FranchiseDocumentCategory.ARTWORKS_MARKETING
                    doc.is_active = True
                    with path.open("rb") as fh:
                        doc.file.save(path.name, File(fh), save=False)
                    doc.save()
                    updated += 1
                else:
                    doc = FranchiseDocument(
                        franchise=None,
                        category=FranchiseDocumentCategory.ARTWORKS_MARKETING,
                        title=title,
                        source_path=source_path,
                        academic_year="AY 2026-27",
                        is_active=True,
                    )
                    with path.open("rb") as fh:
                        doc.file.save(path.name, File(fh), save=False)
                    doc.save()
                    created += 1
                self.stdout.write(self.style.SUCCESS(f"Saved to DB: {source_path}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. created={created} updated={updated} skipped={skipped} missing={missing} dry_run={dry_run}"
            )
        )
