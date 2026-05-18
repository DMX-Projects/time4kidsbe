"""
Print where uploads are stored and whether DB paths exist on disk.

  python manage.py diagnose_media
"""

from __future__ import annotations

import os

from django.conf import settings
from django.core.management.base import BaseCommand

from gallery.models import MediaItem
from common.models import HeroSlide


class Command(BaseCommand):
    help = "Show MEDIA_ROOT, list hero_slides/gallery files, and match DB rows to disk."

    def handle(self, *args, **options):
        root = os.path.realpath(str(settings.MEDIA_ROOT))
        self.stdout.write(self.style.SUCCESS(f"MEDIA_ROOT = {root}"))
        self.stdout.write(f"MEDIA_URL  = {settings.MEDIA_URL}")
        self.stdout.write("")

        for sub in ("hero_slides", "gallery"):
            folder = os.path.join(root, sub)
            self.stdout.write(f"--- {sub}/ ---")
            if not os.path.isdir(folder):
                self.stdout.write(self.style.ERROR(f"  Folder missing: {folder}"))
                continue
            names = sorted(os.listdir(folder))[:20]
            self.stdout.write(f"  Files on disk ({len(os.listdir(folder))} total, showing up to 20):")
            for name in names:
                self.stdout.write(f"    {name}")

        self.stdout.write("\n--- Hero slides (database) ---")
        for slide in HeroSlide.objects.filter(is_active=True).order_by("order")[:10]:
            rel = ""
            if slide.image:
                rel = slide.image.name
            full = os.path.join(root, rel) if rel else ""
            ok = os.path.isfile(full) if rel else False
            status = self.style.SUCCESS("OK") if ok else self.style.ERROR("MISSING")
            self.stdout.write(f"  [{status}] id={slide.id}  {rel}")

        self.stdout.write("\n--- Gallery images (database, last 10) ---")
        qs = MediaItem.objects.exclude(file="").filter(media_type="image").order_by("-id")[:10]
        for item in qs:
            rel = item.file.name if item.file else ""
            full = os.path.join(root, rel) if rel else ""
            ok = os.path.isfile(full) if rel else False
            status = self.style.SUCCESS("OK") if ok else self.style.ERROR("MISSING")
            self.stdout.write(f"  [{status}] id={item.id}  {rel}")

        self.stdout.write(
            "\nIf you see MISSING but you uploaded: MEDIA_ROOT in .env may point elsewhere, "
            "or gunicorn must be restarted after deploy.\n"
            "Test URL (replace filename): "
            f"https://www.timekidspreschools.in/api/cms-files/gallery/FILENAME.jpg\n"
        )
