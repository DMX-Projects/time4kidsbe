"""
Import franchise LP states/cities from kids_stateandcities.xls.

Normalizes messy spellings (Bangalore/Bengaluru, Cochin/Kochi, etc.) and
merges duplicates into one canonical city per state.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from common.models import City, State

FRANCHISE_LP_STATES = (
    "Tamil Nadu",
    "Kerala",
    "Karnataka",
    "Andhra Pradesh",
    "Telangana",
    "Maharashtra",
)

STATE_ALIASES = {
    "tamil nadu": "Tamil Nadu",
    "tamilnadu": "Tamil Nadu",
    "kerala": "Kerala",
    "karnataka": "Karnataka",
    "andhra pradesh": "Andhra Pradesh",
    "andra pradesh": "Andhra Pradesh",
    "telangana": "Telangana",
    "telengana": "Telangana",
    "telanaga": "Telangana",
    "telanagana": "Telangana",
    "maharashtra": "Maharashtra",
    "maharastra": "Maharashtra",
}

# Map any spelling → one canonical display name (Title Case preferred).
CITY_ALIASES = {
    # Karnataka
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
    "mysore": "Mysuru",
    "mysuru": "Mysuru",
    "mangalore": "Mangaluru",
    "mangaluru": "Mangaluru",
    "belgaum": "Belagavi",
    "belagavi": "Belagavi",
    "huballi": "Hubballi",
    "hubli": "Hubballi",
    "hubballi": "Hubballi",
    "shimoga": "Shivamogga",
    "shivamogga": "Shivamogga",
    "tumkur": "Tumakuru",
    "tumakuru": "Tumakuru",
    "dharwad": "Dharwad",
    "hassan": "Hassan",
    "udupi": "Udupi",
    # Kerala
    "cochin": "Kochi",
    "kochi": "Kochi",
    "ernakulam": "Ernakulam",
    "trivandrum": "Thiruvananthapuram",
    "thiruvananthapuram": "Thiruvananthapuram",
    "calicut": "Kozhikode",
    "kozhikode": "Kozhikode",
    "alleppey": "Alappuzha",
    "alapuzha": "Alappuzha",
    "alappuzha": "Alappuzha",
    "aluva": "Aluva",
    "thrissur": "Thrissur",
    "kollam": "Kollam",
    "kottayam": "Kottayam",
    "palakkad": "Palakkad",
    "malappuram": "Malappuram",
    "pathanamthitta": "Pathanamthitta",
    "idukki": "Idukki",
    "kannur": "Kannur",
    "kasaragod": "Kasaragod",
    "perinthalamanna": "Perinthalmanna",
    "perinthalmanna": "Perinthalmanna",
    # Tamil Nadu
    "chennai": "Chennai",
    "coimbatore": "Coimbatore",
    "madurai": "Madurai",
    "trichy": "Tiruchirappalli",
    "tiruchirappalli": "Tiruchirappalli",
    "tiruchirapalli": "Tiruchirappalli",
    "tirunelveli": "Tirunelveli",
    "tiruppur": "Tiruppur",
    "tirupur": "Tiruppur",
    "vellore": "Vellore",
    "salem": "Salem",
    "erode": "Erode",
    "hosur": "Hosur",
    "tanjore": "Thanjavur",
    "thanjavur": "Thanjavur",
    "cuddalore": "Cuddalore",
    "kanchipuram": "Kanchipuram",
    "chengalpattu": "Chengalpattu",
    "namakkal": "Namakkal",
    "karur": "Karur",
    "krishnagiri": "Krishnagiri",
    "pudukkottai": "Pudukkottai",
    "pudukottai": "Pudukkottai",
    "ramanathapuram": "Ramanathapuram",
    "ramnathapuram": "Ramanathapuram",
    "rajapalayam": "Rajapalayam",
    "mayiladuthurai": "Mayiladuthurai",
    "mettupalayam": "Mettupalayam",
    "gudiyatham": "Gudiyatham",
    "guduvancherry": "Guduvancheri",
    "guduvancheri": "Guduvancheri",
    "perungalathur": "Perungalathur",
    "pattabiram": "Pattabiram",
    "annanagar": "Anna Nagar",
    "anna nagar": "Anna Nagar",
    "tiruvallur": "Tiruvallur",
    "tiruvannamalai": "Tiruvannamalai",
    "sivagangai": "Sivagangai",
    "paramakudi": "Paramakudi",
    "thiruthangal": "Thiruthangal",
    "vallioor": "Vallioor",
    "ariyalur": "Ariyalur",
    "arcot": "Arcot",
    "ranipet": "Ranipet",
    "keeranur": "Keeranur",
    "lakshmangudi": "Lakshmangudi",
    "sethumadai": "Sethumadai",
    # Andhra Pradesh
    "vizag": "Visakhapatnam",
    "visakhapatnam": "Visakhapatnam",
    "visakapatnam": "Visakhapatnam",
    "vijayawada": "Vijayawada",
    "guntur": "Guntur",
    "guntakal": "Guntakal",
    "nellore": "Nellore",
    "kurnool": "Kurnool",
    "tirupati": "Tirupati",
    "rajahmundry": "Rajahmundry",
    "eluru": "Eluru",
    "srikakulam": "Srikakulam",
    "tenali": "Tenali",
    "cuddapah": "Kadapa",
    "kadapa": "Kadapa",
    "ravulapalem": "Ravulapalem",
    # Telangana
    "hyderabad": "Hyderabad",
    "secunderabad": "Secunderabad",
    "warangal": "Warangal",
    "nizamabad": "Nizamabad",
    "karimnagar": "Karimnagar",
    "godavarikhani": "Godavarikhani",
    "tandur": "Tandur",
    # Maharashtra
    "mumbai": "Mumbai",
    "pune": "Pune",
    "nagpur": "Nagpur",
    "nashik": "Nashik",
    "nasik": "Nashik",
}

JUNK_CITIES = {
    "null",
    "testcity",
    "test",
    "na",
    "n/a",
    "none",
}


def _norm_key(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip().lower())
    text = text.replace("-", " ")
    return text


def canonicalize_state(raw: str) -> str | None:
    key = _norm_key(raw)
    return STATE_ALIASES.get(key)


def canonicalize_city(raw: str, state_name: str) -> str | None:
    key = _norm_key(raw)
    if not key or key in JUNK_CITIES:
        return None
    # Skip rows where city is actually a state name
    if key in STATE_ALIASES or key == _norm_key(state_name):
        return None
    if key in CITY_ALIASES:
        city = CITY_ALIASES[key]
    else:
        cleaned = re.sub(r"\s+", " ", str(raw).strip())
        if len(cleaned) < 2:
            return None
        city = cleaned.title() if cleaned.isupper() or cleaned.islower() else cleaned

    # Guard against common mis-tagged rows in the XLS
    if city == "Hyderabad" and state_name == "Andhra Pradesh":
        return None
    if city == "Secunderabad" and state_name == "Andhra Pradesh":
        return None
    return city


class Command(BaseCommand):
    help = "Import/merge states & cities from data/kids_stateandcities.xls for franchise LP."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default="data/kids_stateandcities.xls",
            help="Path to XLS relative to time4kidsbe or absolute.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be imported without writing.",
        )

    def handle(self, *args, **options):
        try:
            import xlrd
        except ImportError as exc:
            raise CommandError("Install xlrd==1.2.0 to read .xls files") from exc

        path = Path(options["file"])
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        book = xlrd.open_workbook(str(path))
        sheet = book.sheet_by_name("Sheet1")
        headers = [str(sheet.cell_value(0, c)).strip() for c in range(sheet.ncols)]
        try:
            state_idx = headers.index("state")
            city_idx = headers.index("City")
        except ValueError as exc:
            raise CommandError(f"Sheet1 must have 'state' and 'City' columns. Found: {headers}") from exc

        by_state: dict[str, set[str]] = defaultdict(set)
        skipped = 0
        for row in range(1, sheet.nrows):
            state = canonicalize_state(sheet.cell_value(row, state_idx))
            if not state or state not in FRANCHISE_LP_STATES:
                skipped += 1
                continue
            city = canonicalize_city(sheet.cell_value(row, city_idx), state)
            if not city:
                skipped += 1
                continue
            by_state[state].add(city)

        self.stdout.write(self.style.NOTICE("Normalized cities from XLS:"))
        for state in FRANCHISE_LP_STATES:
            cities = sorted(by_state.get(state, set()))
            self.stdout.write(f"  {state}: {len(cities)} -> {', '.join(cities[:12])}{' ...' if len(cities) > 12 else ''}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(f"Dry run only. Skipped rows: {skipped}"))
            return

        created_states = 0
        created_cities = 0
        merged_away = 0

        with transaction.atomic():
            for state_name in FRANCHISE_LP_STATES:
                state_obj, was_created = State.objects.get_or_create(name=state_name)
                if was_created:
                    created_states += 1

                # Collapse existing alias duplicates in DB for this state
                existing = list(City.objects.filter(state=state_obj))
                keep_by_canonical: dict[str, City] = {}
                for city_obj in existing:
                    canonical = canonicalize_city(city_obj.name, state_name)
                    if not canonical:
                        city_obj.delete()
                        merged_away += 1
                        continue
                    key = canonical.casefold()
                    if key in keep_by_canonical:
                        # Duplicate alias — remove this row
                        city_obj.delete()
                        merged_away += 1
                        continue
                    if city_obj.name != canonical:
                        city_obj.name = canonical
                        city_obj.save(update_fields=["name"])
                    keep_by_canonical[key] = city_obj

                for city_name in sorted(by_state.get(state_name, set())):
                    key = city_name.casefold()
                    if key in keep_by_canonical:
                        continue
                    City.objects.create(state=state_obj, name=city_name)
                    created_cities += 1
                    keep_by_canonical[key] = None  # type: ignore

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. states_created={created_states} cities_created={created_cities} "
                f"duplicates_removed={merged_away} skipped_xls_rows={skipped}"
            )
        )

        self.stdout.write(self.style.NOTICE("Final franchise-LP city counts:"))
        for state_name in FRANCHISE_LP_STATES:
            count = City.objects.filter(state__name=state_name).count()
            self.stdout.write(f"  {state_name}: {count}")
