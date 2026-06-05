from datetime import date, timedelta

from django.core.management.base import BaseCommand

from franchises.models import Franchise
from students.models import HomeworkAssignment

CLASS_LABELS = [
    "Play Group",
    "Nursery",
    "PP-1 / Junior KG / LKG",
    "PP-2 / Senior KG / UKG",
    "Summer Programs / Day Care",
]

HOMEWORK_TITLES = [
    "Alphabet practice",
    "Number counting",
    "EVS – nature walk",
    "English reading",
    "Creative drawing",
    "Rhymes & songs",
    "Shape recognition",
    "Story time activity",
    "Colouring worksheet",
    "General revision",
    "Handwriting practice",
    "Science experiment",
    "Music & movement",
    "Puzzle solving",
    "Group activity",
]

DATE_SLOTS = [
    (1, 8),
    (1, 22),
    (2, 5),
    (2, 19),
    (3, 7),
    (3, 21),
    (4, 4),
    (4, 18),
    (5, 9),
    (5, 23),
    (6, 6),
    (6, 20),
    (7, 11),
    (8, 8),
    (9, 12),
]

MONTH_DAY_SLOTS = DATE_SLOTS[:10]


def iter_year_days(year: int):
    d = date(year, 1, 1)
    end = date(year, 12, 31)
    while d <= end:
        yield d
        d += timedelta(days=1)


class Command(BaseCommand):
    help = (
        "Seed sample homework for a franchise. "
        "Use --daily-full-year for every day in a year (15 per day, all classes). "
        "Default: sparse school dates only."
    )

    def add_arguments(self, parser):
        parser.add_argument("--franchise-id", type=int, default=None)
        parser.add_argument("--years", default="2025", help="Comma-separated years")
        parser.add_argument(
            "--per-date",
            type=int,
            default=15,
            help="Homework per day (default: 15). With --daily-full-year: 3 per class × 5 classes.",
        )
        parser.add_argument(
            "--daily-full-year",
            action="store_true",
            help="Seed every calendar day in each year (all months, all classes, daily).",
        )
        parser.add_argument(
            "--per-class",
            type=int,
            default=None,
            help="Legacy: N homework per class per year on sparse dates",
        )
        parser.add_argument(
            "--replace-year",
            action="store_true",
            help="Delete existing homework for this franchise/year before seeding",
        )
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            default=True,
            help="Skip dates that already have homework (default: on)",
        )
        parser.add_argument(
            "--no-skip-existing",
            action="store_false",
            dest="skip_existing",
            help="Add homework even when a date already has rows",
        )

    def handle(self, *args, **options):
        franchise_id = options["franchise_id"]
        years = [int(y.strip()) for y in options["years"].split(",") if y.strip()]
        per_date = max(1, min(options["per_date"], 15))
        per_class = options["per_class"]
        daily_full_year = options["daily_full_year"]
        dry_run = options["dry_run"]
        skip_existing = options["skip_existing"]
        replace_year = options["replace_year"]

        if franchise_id:
            franchise = Franchise.objects.filter(pk=franchise_id).first()
        else:
            franchise = Franchise.objects.order_by("id").first()

        if not franchise:
            self.stderr.write(self.style.ERROR("No franchise found."))
            return

        if replace_year and not dry_run:
            deleted, _ = HomeworkAssignment.objects.filter(
                franchise=franchise,
                assigned_date__year__in=years,
            ).delete()
            self.stdout.write(self.style.WARNING(f"Removed {deleted} existing homework row(s) for {years}."))

        existing_dates: set[date] = set()
        if skip_existing and not replace_year:
            existing_dates = set(
                HomeworkAssignment.objects.filter(franchise=franchise, assigned_date__year__in=years)
                .values_list("assigned_date", flat=True)
                .distinct()
            )

        to_create: list[HomeworkAssignment] = []

        if daily_full_year:
            per_class_per_day = max(1, per_date // len(CLASS_LABELS))
            for year in years:
                for assigned in iter_year_days(year):
                    if skip_existing and assigned in existing_dates:
                        continue
                    item_index = 0
                    for class_name in CLASS_LABELS:
                        for _ in range(per_class_per_day):
                            title = HOMEWORK_TITLES[item_index % len(HOMEWORK_TITLES)]
                            to_create.append(
                                HomeworkAssignment(
                                    franchise=franchise,
                                    student=None,
                                    class_name=class_name,
                                    assigned_date=assigned,
                                    title=title,
                                    description=f"Daily homework for {class_name} ({assigned.isoformat()}).",
                                )
                            )
                            item_index += 1
                    # Fill remainder up to per_date (15) rotating classes
                    while item_index < per_date:
                        class_name = CLASS_LABELS[item_index % len(CLASS_LABELS)]
                        title = HOMEWORK_TITLES[item_index % len(HOMEWORK_TITLES)]
                        to_create.append(
                            HomeworkAssignment(
                                franchise=franchise,
                                student=None,
                                class_name=class_name,
                                assigned_date=assigned,
                                title=title,
                                description=f"Daily homework for {class_name} ({assigned.isoformat()}).",
                            )
                        )
                        item_index += 1
        elif per_class is not None:
            count = max(1, min(per_class, len(HOMEWORK_TITLES)))
            for year in years:
                for class_name in CLASS_LABELS:
                    for i in range(count):
                        month, day = MONTH_DAY_SLOTS[i % len(MONTH_DAY_SLOTS)]
                        assigned = date(year, month, day)
                        if skip_existing and assigned in existing_dates:
                            continue
                        to_create.append(
                            HomeworkAssignment(
                                franchise=franchise,
                                student=None,
                                class_name=class_name,
                                assigned_date=assigned,
                                title=HOMEWORK_TITLES[i % len(HOMEWORK_TITLES)],
                                description=f"Sample homework for {class_name} ({assigned.isoformat()}).",
                            )
                        )
        else:
            for year in years:
                for month, day in DATE_SLOTS:
                    assigned = date(year, month, day)
                    if skip_existing and assigned in existing_dates:
                        continue
                    for i in range(per_date):
                        class_name = CLASS_LABELS[i % len(CLASS_LABELS)]
                        to_create.append(
                            HomeworkAssignment(
                                franchise=franchise,
                                student=None,
                                class_name=class_name,
                                assigned_date=assigned,
                                title=HOMEWORK_TITLES[i % len(HOMEWORK_TITLES)],
                                description=f"Sample homework for {class_name} on {assigned.isoformat()}.",
                            )
                        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run: would create {len(to_create)} rows for franchise #{franchise.pk} ({franchise})"
                )
            )
            return

        if not to_create:
            self.stdout.write(self.style.WARNING("No new homework to create."))
            return

        created = HomeworkAssignment.objects.bulk_create(to_create, batch_size=500)
        if daily_full_year:
            mode = f"{per_date}/day × 365 days × all {len(CLASS_LABELS)} classes"
        elif per_class is not None:
            mode = f"{per_class} per class (sparse dates)"
        else:
            mode = f"{per_date} per date × {len(DATE_SLOTS)} sparse dates"
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(created)} homework for franchise #{franchise.pk} ({franchise}) — {mode}."
            )
        )
