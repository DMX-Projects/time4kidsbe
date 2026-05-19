"""Keep global FranchiseDocument rows in sync when students kit PDFs change."""

from __future__ import annotations

from documents.models import FranchiseDocument, FranchiseDocumentCategory

from .models import StudentsKitPage


def sync_students_kit_franchise_document(page: StudentsKitPage) -> None:
    """Upsert a global STUDENTS_KIT franchise document keyed by row_key."""
    base_qs = FranchiseDocument.objects.filter(
        source_path=page.row_key,
        franchise__isnull=True,
        category=FranchiseDocumentCategory.STUDENTS_KIT,
    )

    if not page.pdf:
        base_qs.update(is_active=False)
        return

    doc = base_qs.first()
    if not doc:
        doc = FranchiseDocument(
            source_path=page.row_key,
            franchise=None,
            category=FranchiseDocumentCategory.STUDENTS_KIT,
        )

    doc.title = (page.link_label or page.short_label or page.title).strip() or page.title
    doc.academic_year = page.academic_year or ""
    doc.order = page.order
    doc.is_active = page.is_active
    doc.file = page.pdf
    doc.save()
