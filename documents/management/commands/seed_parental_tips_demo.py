"""Seed demo Parental Tips (PDF, audio link, video link) for HO + one centre."""

from __future__ import annotations

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from documents.models import DocumentCategory, ParentDocument
from franchises.models import Franchise

# Minimal valid PDF for parent-app streaming tests.
MINIMAL_PDF = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer<</Size 4/Root 1 0 R>>
startxref
196
%%EOF
"""

DEMO_AUDIO_URL = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
DEMO_VIDEO_URL = "https://www.youtube.com/embed/dQw4w9WgXcQ"


class Command(BaseCommand):
    help = "Create demo Parental Tips for head office and a centre (default: Domalaguda)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--centre",
            default="Domalaguda",
            help="Franchise name contains this string (default: Domalaguda).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete previous demo rows (title starts with [HO Demo] or [Centre Demo]).",
        )

    def handle(self, *args, **options):
        name = (options.get("centre") or "Domalaguda").strip()
        franchise = Franchise.objects.filter(name__icontains=name).order_by("id").first()
        if franchise is None:
            self.stderr.write(self.style.ERROR(f"No franchise matching {name!r}"))
            return

        if options.get("clear"):
            deleted, _ = ParentDocument.objects.filter(
                category=DocumentCategory.PARENTING_TIPS,
                title__regex=r"^\[(HO|Centre) Demo\]",
            ).delete()
            self.stdout.write(f"Removed {deleted} previous demo row(s).")

        now = timezone.now()
        created_ids: list[int] = []

        ho_rows = [
            {
                "title": "[HO Demo] Parental tip - PDF",
                "description": "Head office PDF for Domalaguda parents (soft launch test).",
                "file_name": "ho-parental-tip-demo.pdf",
                "file_bytes": MINIMAL_PDF,
            },
            {
                "title": "[HO Demo] Parental tip - Audio link",
                "description": "Head office audio link for Domalaguda parents.",
                "audio_embed_url": DEMO_AUDIO_URL,
            },
            {
                "title": "[HO Demo] Parental tip - Video link",
                "description": "Head office video link for Domalaguda parents.",
                "video_embed_url": DEMO_VIDEO_URL,
            },
        ]

        for spec in ho_rows:
            doc = ParentDocument(
                franchise=None,
                category=DocumentCategory.PARENTING_TIPS,
                title=spec["title"],
                description=spec["description"],
                academic_year="AY 2026-27",
                is_active=True,
                publish_scope=ParentDocument.PublishScope.ONE_CENTRE,
                target_franchise_ids=[franchise.pk],
                audio_embed_url=spec.get("audio_embed_url", ""),
                video_embed_url=spec.get("video_embed_url", ""),
            )
            if spec.get("file_bytes"):
                doc.file.save(spec["file_name"], ContentFile(spec["file_bytes"]), save=False)
            doc.save()
            ParentDocument.objects.filter(pk=doc.pk).update(updated_at=now)
            created_ids.append(doc.pk)
            self.stdout.write(self.style.SUCCESS(f"HO  #{doc.pk}  {doc.title}"))

        centre_rows = [
            {
                "title": "[Centre Demo] Parental tip - PDF",
                "description": f"{franchise.name} centre PDF for parents (soft launch test).",
                "file_name": "centre-parental-tip-demo.pdf",
                "file_bytes": MINIMAL_PDF,
            },
            {
                "title": "[Centre Demo] Parental tip - Audio link",
                "description": f"{franchise.name} centre audio link.",
                "audio_embed_url": DEMO_AUDIO_URL,
            },
            {
                "title": "[Centre Demo] Parental tip - Video link",
                "description": f"{franchise.name} centre video link.",
                "video_embed_url": DEMO_VIDEO_URL,
            },
        ]

        for spec in centre_rows:
            doc = ParentDocument(
                franchise=franchise,
                category=DocumentCategory.PARENTING_TIPS,
                title=spec["title"],
                description=spec["description"],
                academic_year="AY 2026-27",
                is_active=True,
                publish_scope=ParentDocument.PublishScope.ONE_CENTRE,
                target_franchise_ids=[franchise.pk],
                audio_embed_url=spec.get("audio_embed_url", ""),
                video_embed_url=spec.get("video_embed_url", ""),
            )
            if spec.get("file_bytes"):
                doc.file.save(spec["file_name"], ContentFile(spec["file_bytes"]), save=False)
            doc.save()
            ParentDocument.objects.filter(pk=doc.pk).update(updated_at=now)
            created_ids.append(doc.pk)
            self.stdout.write(self.style.SUCCESS(f"Centre  #{doc.pk}  {doc.title}  -> {franchise.name}"))

        self.stdout.write("")
        self.stdout.write(
            self.style.NOTICE(
                f"Created {len(created_ids)} parental tips for {franchise.name} (id={franchise.pk}). "
                "Parents at this centre should see them under Parental Tips, Notifications, and calendar-attendance."
            )
        )
