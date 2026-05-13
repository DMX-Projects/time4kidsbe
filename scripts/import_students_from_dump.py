"""
Import parents + students from the legacy SQL dump into the Django models.

Fixes problems in the old `migrate_students.py`:
- It hardcoded `franchise_id=29` and `user_id=1`, which makes every parent/student show only under one centre.
- It inserted ParentProfile rows without creating per-parent `accounts.User` rows.

This script:
- Reads each row, maps `Centre` -> `franchises.Franchise` (by slug/name).
- Creates/gets a parent `accounts.User` (role=PARENT) per unique parent (email/phone).
- Creates/gets `franchises.ParentProfile` linked to that franchise.
- Creates `students.StudentProfile` linked to that ParentProfile.

Run:
  cd time4kidsbe
  .\.venv\Scripts\python.exe scripts\import_students_from_dump.py --sql "C:\\timekids_migration\\timepreschool_timekids.sql"

Optional:
  --dry-run   (no DB writes)
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from typing import Iterable


def clean_phone(val: object) -> str:
    return re.sub(r"[^0-9]", "", str(val or ""))[:10]


def safe(val: object, max_len: int | None = None) -> str:
    s = str(val or "").strip()
    return s[:max_len] if max_len else s


@dataclass(frozen=True)
class LegacyRow:
    centre: str
    city: str
    student_name: str
    class_name: str
    roll_number: str
    parent_name: str
    email: str
    phone: str


def parse_students(sql_file: str) -> Iterable[LegacyRow]:
    """
    The legacy dump contains multi-row INSERT statements. This parser is intentionally tolerant:
    - it looks for tuple-like lines starting with "("
    - uses eval() like the old script did (only safe if you trust the dump file)
    """
    with open(sql_file, "r", encoding="latin-1", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line.startswith("("):
                continue
            try:
                values = eval(line.rstrip(",;"))  # noqa: S307 - trusted local migration file
            except Exception:
                continue

            # Expected columns (based on old script):
            # 0 Sno, 1 State, 2 City, 3 Centre, 4 StudentName, 5 Class, 6 Idcardno, 7 Password,
            # 8 batch_num, 9 ParentName, 10 Emailid, 11 Mobileno, 12 Year
            if not isinstance(values, tuple) or len(values) < 13:
                continue

            yield LegacyRow(
                centre=safe(values[3], 255),
                city=safe(values[2], 100),
                student_name=safe(values[4], 200),
                class_name=safe(values[5], 50),
                roll_number=safe(values[6], 50),
                parent_name=safe(values[9], 255),
                email=safe(values[10], 254).lower(),
                phone=clean_phone(values[11]),
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sql", required=True, help="Path to legacy SQL dump file")
    parser.add_argument("--dry-run", action="store_true", help="Parse and map, but do not write to DB")
    parser.add_argument("--limit", type=int, default=0, help="Process only N rows (0 = all)")
    args = parser.parse_args()

    backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "time4kids_be.settings")

    import django  # noqa: PLC0415

    django.setup()

    from django.db import transaction  # noqa: PLC0415
    from django.utils.text import slugify  # noqa: PLC0415

    from accounts.models import User, UserRole  # noqa: PLC0415
    from franchises.models import Franchise, ParentProfile  # noqa: PLC0415
    from students.models import StudentProfile  # noqa: PLC0415

    # Build lookup maps
    franchises = list(Franchise.objects.all().only("id", "name", "slug"))
    by_slug = {str(f.slug).strip().lower(): f for f in franchises if f.slug}
    by_name = {str(f.name).strip().lower(): f for f in franchises if f.name}

    processed = 0
    created_users = 0
    created_parents = 0
    created_students = 0
    franchise_misses = 0

    def franchise_for_row(r: LegacyRow) -> Franchise | None:
        key_slug = slugify(r.centre).strip().lower()
        if key_slug and key_slug in by_slug:
            return by_slug[key_slug]
        key_name = r.centre.strip().lower()
        if key_name in by_name:
            return by_name[key_name]
        # Fuzzy fallback (contains match)
        if r.centre:
            needle = r.centre.strip().lower()
            for f in franchises:
                if needle and needle in (f.name or "").strip().lower():
                    return f
        return None

    # Batch commits to keep it reasonably fast and safe.
    BATCH = 500
    buffer = []

    for row in parse_students(args.sql):
        buffer.append(row)
        if len(buffer) < BATCH:
            continue

        with transaction.atomic():
            for r in buffer:
                if args.limit and processed >= args.limit:
                    break

                processed += 1

                f = franchise_for_row(r)
                if not f:
                    franchise_misses += 1
                    continue

                # Identify a parent uniquely.
                # Prefer email; if missing, synthesize one from phone/centre so `User.email` stays unique.
                parent_email = (r.email or "").strip().lower()
                if not parent_email:
                    suffix = r.phone or slugify(r.centre) or "unknown"
                    parent_email = f"parent-{suffix}@time4kids.local"

                if args.dry_run:
                    continue

                user, u_created = User.objects.get_or_create(
                    email=parent_email,
                    defaults={
                        "role": UserRole.PARENT,
                        "username": (parent_email.split("@")[0][:150] or None),
                        "full_name": r.parent_name or "",
                        "is_active": True,
                    },
                )
                if u_created:
                    user.set_unusable_password()
                    user.save(update_fields=["password"])
                    created_users += 1

                # Ensure role + name are sane (migration data can be messy).
                changed = False
                if (user.role or "").upper() != UserRole.PARENT:
                    user.role = UserRole.PARENT
                    changed = True
                if r.parent_name and (user.full_name or "").strip() != r.parent_name.strip():
                    user.full_name = r.parent_name.strip()[:255]
                    changed = True
                if changed:
                    user.save(update_fields=["role", "full_name"])

                pp, pp_created = ParentProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        "franchise": f,
                        "child_name": "",
                        "phone": r.phone,
                        "city": r.city,
                    },
                )
                if not pp_created and pp.franchise_id != f.id:
                    # If the same parent exists under another centre, keep the earliest centre;
                    # change only when current is empty.
                    # (You can customize this rule later.)
                    pass
                if pp_created:
                    created_parents += 1

                # Student name split
                parts = (r.student_name or "").strip().split()
                first = parts[0] if parts else (r.student_name or "").strip()
                last = " ".join(parts[1:]) if len(parts) > 1 else ""

                # Avoid duplicates (same roll_number within same parent + class).
                exists = StudentProfile.objects.filter(
                    parent=pp,
                    roll_number=r.roll_number,
                    class_name=r.class_name,
                    first_name=first,
                ).exists()
                if exists:
                    continue

                StudentProfile.objects.create(
                    parent=pp,
                    first_name=first[:100] or "(no name)",
                    last_name=last[:100],
                    class_name=r.class_name or "",
                    section="",
                    roll_number=r.roll_number or "",
                    emergency_contact=r.phone,
                    is_active=True,
                )
                created_students += 1

        buffer = []
        if processed and processed % 5000 == 0:
            print(
                f"PROGRESS processed={processed} users+{created_users} parents+{created_parents} students+{created_students} centre_miss={franchise_misses}"
            )

        if args.limit and processed >= args.limit:
            break

    # Flush remainder
    if buffer and not (args.limit and processed >= args.limit):
        with transaction.atomic():
            for r in buffer:
                if args.limit and processed >= args.limit:
                    break
                processed += 1
                f = franchise_for_row(r)
                if not f:
                    franchise_misses += 1
                    continue
                if args.dry_run:
                    continue
                parent_email = (r.email or "").strip().lower()
                if not parent_email:
                    suffix = r.phone or slugify(r.centre) or "unknown"
                    parent_email = f"parent-{suffix}@time4kids.local"
                user, u_created = User.objects.get_or_create(
                    email=parent_email,
                    defaults={
                        "role": UserRole.PARENT,
                        "username": (parent_email.split("@")[0][:150] or None),
                        "full_name": r.parent_name or "",
                        "is_active": True,
                    },
                )
                if u_created:
                    user.set_unusable_password()
                    user.save(update_fields=["password"])
                    created_users += 1
                pp, pp_created = ParentProfile.objects.get_or_create(
                    user=user,
                    defaults={"franchise": f, "child_name": "", "phone": r.phone, "city": r.city},
                )
                if pp_created:
                    created_parents += 1
                parts = (r.student_name or "").strip().split()
                first = parts[0] if parts else (r.student_name or "").strip()
                last = " ".join(parts[1:]) if len(parts) > 1 else ""
                exists = StudentProfile.objects.filter(
                    parent=pp,
                    roll_number=r.roll_number,
                    class_name=r.class_name,
                    first_name=first,
                ).exists()
                if exists:
                    continue
                StudentProfile.objects.create(
                    parent=pp,
                    first_name=first[:100] or "(no name)",
                    last_name=last[:100],
                    class_name=r.class_name or "",
                    section="",
                    roll_number=r.roll_number or "",
                    emergency_contact=r.phone,
                    is_active=True,
                )
                created_students += 1

    print(
        f"DONE processed={processed} created_users={created_users} created_parent_profiles={created_parents} created_students={created_students} centre_miss={franchise_misses} dry_run={args.dry_run}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

