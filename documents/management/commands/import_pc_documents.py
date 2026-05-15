"""
Import centre resource files from the legacy `pc` folder into FranchiseDocument (PostgreSQL).

Usage:
  python manage.py import_pc_documents
  python manage.py import_pc_documents --root "C:\\Users\\Admin1\\Desktop\\pc"
  python manage.py import_pc_documents --dry-run
  python manage.py import_pc_documents --update   # replace file when source_path already exists
"""

from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from documents.models import FranchiseDocument, FranchiseDocumentCategory


def normalize_source_path(relative: str) -> str:
    return relative.replace("\\", "/").strip("/")


def title_from_filename(name: str) -> str:
    stem = Path(name).stem
    return stem.replace("_", " ").strip() or name


def academic_year_from_path(relative: str) -> str:
    m = re.search(r"20\d{2}[-/]20\d{2}|AY[- ]?20\d{2}[-/]20\d{2}|20\d{2}-\d{2}", relative, re.I)
    return m.group(0).replace("/", "-") if m else ""


def category_for_path(relative: str) -> str:
    rel = relative.replace("\\", "/")
    parts = rel.split("/")
    top = parts[0].lower() if parts else ""
    name = Path(rel).name.lower()

    rules: list[tuple[str, str]] = [
        (r"^holidayslist", FranchiseDocumentCategory.HOLIDAY_LISTS),
        (r"^study-material", FranchiseDocumentCategory.ACADEMIC_DOCUMENTS),
        (r"^welcome-letters", FranchiseDocumentCategory.WELCOME_LETTERS),
        (r"^refreshercourse|^refresher-course", FranchiseDocumentCategory.REFRESHER_COURSE),
        (r"^summercamp", FranchiseDocumentCategory.SUMMER_CAMP),
        (r"^social-media", FranchiseDocumentCategory.SOCIAL_MEDIA_SUPPORT),
        (r"^rhymes", FranchiseDocumentCategory.WATCH_HEAR_LEARN),
        (r"^admission-counselling", FranchiseDocumentCategory.ADMISSION_COUNSELLING),
        (r"^academic-documents", FranchiseDocumentCategory.ACADEMIC_DOCUMENTS),
        (r"^term-ii", FranchiseDocumentCategory.ACADEMIC_DOCUMENTS),
    ]
    for pattern, cat in rules:
        if re.search(pattern, top, re.I):
            return cat

    if "students kit" in name:
        return FranchiseDocumentCategory.STUDENTS_KIT
    if "student transfer" in name:
        return FranchiseDocumentCategory.STUDENT_TRANSFER_POLICY
    if name.startswith("sop"):
        return FranchiseDocumentCategory.SOP
    if "infrastructure" in name:
        return FranchiseDocumentCategory.INFRASTRUCTURE_MANUAL
    if "lease" in name:
        return FranchiseDocumentCategory.LEASE_AGREEMENT_DOCUMENTS
    if "bonafide" in name or "transfer certificate" in name:
        return FranchiseDocumentCategory.FORMATS
    if "report card comment" in name:
        return FranchiseDocumentCategory.REPORT_CARD_COMMENTS
    if "counselling tool" in name or "report cards" in name:
        return FranchiseDocumentCategory.COUNSELLING_TOOLS
    if "referral" in name and "incentive" in name:
        return FranchiseDocumentCategory.FRANCHISE_REFERRAL_INCENTIVES
    if "indent" in name:
        return FranchiseDocumentCategory.INDENT_DOCUMENTS
    if "concept room" in name or "class display" in name or "artistic wall" in name:
        return FranchiseDocumentCategory.CONCEPT_ROOM_DISPLAYS
    if "parents orientation" in name:
        return FranchiseDocumentCategory.PARENT_ORIENTATION
    if any(x in name for x in ("artwork", "admission", "marketing", "banner", "vijayadhasami", "aksharabhyasam")):
        return FranchiseDocumentCategory.ARTWORKS_MARKETING
    if "parenting" in name:
        return FranchiseDocumentCategory.PARENTING_TIPS

    return FranchiseDocumentCategory.ACADEMIC_DOCUMENTS


class Command(BaseCommand):
    help = "Import files from the legacy pc folder into FranchiseDocument (PostgreSQL)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--root",
            type=str,
            default="",
            help="Folder path (default: settings.PC_DOCUMENTS_ROOT)",
        )
        parser.add_argument("--dry-run", action="store_true", help="Show actions without writing.")
        parser.add_argument(
            "--update",
            action="store_true",
            help="Replace file on disk when source_path already exists.",
        )
        parser.add_argument("--order-start", type=int, default=0, help="Starting order index.")

    def handle(self, *args, **options):
        root_arg = (options.get("root") or "").strip()
        root = Path(root_arg) if root_arg else getattr(settings, "PC_DOCUMENTS_ROOT", None)
        if not root or not Path(root).is_dir():
            raise CommandError(
                "PC folder not found. Set PC_DOCUMENTS_ROOT in .env or pass --root "
                '(e.g. --root "C:\\Users\\Admin1\\Desktop\\pc").'
            )
        root = Path(root).resolve()
        dry_run = options["dry_run"]
        do_update = options["update"]
        order = int(options["order_start"])

        files = sorted(p for p in root.rglob("*") if p.is_file())
        if not files:
            raise CommandError(f"No files under {root}")

        created = updated = skipped = 0

        for file_path in files:
            relative = normalize_source_path(str(file_path.relative_to(root)))
            source_path = relative
            title = title_from_filename(file_path.name)
            category = category_for_path(relative)
            academic_year = academic_year_from_path(relative)

            existing = FranchiseDocument.objects.filter(source_path=source_path).first()

            if existing and not do_update:
                skipped += 1
                continue

            if dry_run:
                action = "UPDATE" if existing else "CREATE"
                self.stdout.write(f"[dry-run] {action} {source_path} → {category} | {title}")
                continue

            with transaction.atomic():
                if existing:
                    doc = existing
                    doc.title = title
                    doc.category = category
                    doc.academic_year = academic_year or doc.academic_year
                    doc.is_active = True
                    with file_path.open("rb") as fh:
                        doc.file.save(file_path.name, File(fh), save=False)
                    doc.save()
                    updated += 1
                    self.stdout.write(self.style.WARNING(f"Updated: {source_path}"))
                else:
                    doc = FranchiseDocument(
                        franchise=None,
                        category=category,
                        title=title,
                        source_path=source_path,
                        academic_year=academic_year,
                        order=order,
                        is_active=True,
                    )
                    with file_path.open("rb") as fh:
                        doc.file.save(file_path.name, File(fh), save=False)
                    doc.save()
                    order += 1
                    created += 1
                    self.stdout.write(self.style.SUCCESS(f"Created: {source_path}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. created={created} updated={updated} skipped={skipped} (dry_run={dry_run})"
            )
        )
