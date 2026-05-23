"""
Fill franchise latitude/longitude from address via OpenStreetMap Nominatim.
Usage: python manage.py geocode_franchises [--dry-run] [--limit 50]
"""
import time
import urllib.parse
import urllib.request

from django.core.management.base import BaseCommand

from franchises.franchise_geo import effective_city, public_franchise_queryset
from franchises.models import Franchise


class Command(BaseCommand):
    help = "Geocode active franchises missing latitude/longitude (Nominatim, 1 req/sec)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Print only; do not save.")
        parser.add_argument("--limit", type=int, default=0, help="Max rows to process (0 = all).")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"] or None

        qs = (
            public_franchise_queryset()
            .filter(latitude__isnull=True)
            .order_by("id")
        )
        if limit:
            qs = qs[:limit]

        updated = 0
        failed = 0
        for franchise in qs:
            query = ", ".join(
                p
                for p in [
                    franchise.address,
                    effective_city(franchise),
                    franchise.get_state_display() if franchise.state else franchise.state,
                    franchise.postal_code,
                    "India",
                ]
                if p
            )
            if not query.strip():
                failed += 1
                continue

            coords = self._nominatim(query)
            if not coords:
                self.stdout.write(self.style.WARNING(f"SKIP {franchise.id} {franchise.name}: no result"))
                failed += 1
                time.sleep(1.1)
                continue

            lat, lng = coords
            self.stdout.write(f"{'[dry] ' if dry_run else ''}OK {franchise.name}: {lat}, {lng}")
            if not dry_run:
                Franchise.objects.filter(pk=franchise.pk).update(latitude=lat, longitude=lng)
            updated += 1
            time.sleep(1.1)

        self.stdout.write(self.style.SUCCESS(f"Done. updated={updated} failed={failed} dry_run={dry_run}"))

    def _nominatim(self, query: str) -> tuple[float, float] | None:
        params = urllib.parse.urlencode(
            {"q": query, "format": "json", "limit": 1, "countrycodes": "in"},
        )
        url = f"https://nominatim.openstreetmap.org/search?{params}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "time4kids-locate-centre/1.0 (contact@timekidspreschools.in)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                import json

                data = json.loads(resp.read().decode())
        except OSError:
            return None
        if not data:
            return None
        try:
            return float(data[0]["lat"]), float(data[0]["lon"])
        except (KeyError, TypeError, ValueError):
            return None
