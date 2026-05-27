"""
Fast legacy import: link all Student_details + Student_details2 rows to users + franchises.

Run:
  cd time4kidsbe
  python scripts/import_students_from_dump.py --sql "C:\\timekids_migration\\timepreschool_timekids.sql"
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass


def clean_phone(val: object) -> str:
    return re.sub(r"[^0-9]", "", str(val or ""))[-10:]


def safe(val: object, max_len: int | None = None) -> str:
    s = str(val or "").strip()
    return s[:max_len] if max_len else s


@dataclass(frozen=True)
class LegacyRow:
    state: str
    centre: str
    city: str
    student_name: str
    class_name: str
    idcardno: str
    password: str
    parent_name: str
    email: str
    phone: str
    year: str


def parse_legacy_students(sql_file: str):
    """Parse ``Student_details`` and ``Student_details2`` INSERT blocks."""
    in_block = False
    block_table = ""

    with open(sql_file, "r", encoding="latin-1", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            upper = line.upper()

            if "INSERT INTO `STUDENT_DETAILS2`" in upper:
                in_block = True
                block_table = "Student_details2"
                continue
            if "INSERT INTO `STUDENT_DETAILS`" in upper:
                in_block = True
                block_table = "Student_details"
                continue

            if in_block and upper.startswith("INSERT INTO ") and "STUDENT_DETAILS" not in upper:
                in_block = False
                block_table = ""

            if not in_block or not line.startswith("("):
                continue

            try:
                values = eval(line.rstrip(",;"))  # noqa: S307
            except Exception:
                continue

            if not isinstance(values, tuple) or len(values) < 13:
                continue

            idcardno = safe(values[6], 50)
            if not idcardno:
                continue

            yield LegacyRow(
                state=safe(values[1], 255),
                centre=safe(values[3], 255),
                city=safe(values[2], 100),
                student_name=safe(values[4], 200),
                class_name=safe(values[5], 50),
                idcardno=idcardno,
                password=safe(values[7], 255),
                parent_name=safe(values[9], 255),
                email=safe(values[10], 254).lower(),
                phone=clean_phone(values[11]),
                year=safe(values[12], 100),
            )


def build_franchise_resolver(franchises):
    from django.utils.text import slugify

    by_slug = {str(f.slug).strip().lower(): f for f in franchises if f.slug}
    by_name = {str(f.name).strip().lower(): f for f in franchises if f.name}
    cache: dict[str, object | None] = {}

    def resolve(centre: str):
        key = (centre or "").strip().lower()
        if not key:
            return None
        if key in cache:
            return cache[key]

        key_slug = slugify(centre).strip().lower()
        if key_slug and key_slug in by_slug:
            cache[key] = by_slug[key_slug]
            return cache[key]

        if key in by_name:
            cache[key] = by_name[key]
            return cache[key]

        matches = [f for f in franchises if key in (f.name or "").strip().lower()]
        if len(matches) == 1:
            cache[key] = matches[0]
            return cache[key]

        compact = re.sub(r"[^a-z0-9]", "", key)
        for f in franchises:
            fname = re.sub(r"[^a-z0-9]", "", (f.name or "").strip().lower())
            if compact and compact == fname:
                cache[key] = f
                return cache[key]

        # Spacing / punctuation variants (e.g. "A. S. Rao Nagar" vs "A.S.Rao Nagar")
        norm = re.sub(r"\s+", " ", re.sub(r"\.\s*", ".", key)).strip()
        for f in franchises:
            fn = re.sub(r"\s+", " ", re.sub(r"\.\s*", ".", (f.name or "").strip().lower())).strip()
            if norm == fn:
                cache[key] = f
                return cache[key]
            if norm in fn or fn in norm:
                matches.append(f)
        if len(matches) == 1:
            cache[key] = matches[0]
            return cache[key]

        cache[key] = None
        return None

    return resolve


def split_name(full: str) -> tuple[str, str]:
    parts = (full or "").strip().split()
    if not parts:
        return "(no name)", ""
    if len(parts) == 1:
        return parts[0][:100], ""
    return parts[0][:100], " ".join(parts[1:])[:100]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sql", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "time4kids_be.settings")

    import django  # noqa: PLC0415

    django.setup()

    from django.db import transaction  # noqa: PLC0415

    from accounts.models import User, UserRole  # noqa: PLC0415
    from franchises.models import Franchise, ParentProfile  # noqa: PLC0415
    from students.models import StudentProfile  # noqa: PLC0415

    franchises = list(Franchise.objects.all())
    franchise_for = build_franchise_resolver(franchises)

    print("Loading users...", flush=True)
    users_by_username = {
        (u.username or "").strip().lower(): u
        for u in User.objects.exclude(username__isnull=True).exclude(username="").only(
            "id", "username", "email", "full_name", "role"
        )
    }
    users_by_email = {}
    for u in User.objects.exclude(email__isnull=True).exclude(email="").only(
        "id", "username", "email", "full_name", "role"
    ):
        users_by_email.setdefault(u.email.strip().lower(), u)

    print("Loading existing profiles...", flush=True)
    parent_by_user_id = {
        pp.user_id: pp
        for pp in ParentProfile.objects.select_related("franchise").only(
            "id", "user_id", "franchise_id", "child_name", "phone", "Emailid", "city"
        )
    }
    students_by_idcard = {
        (s.Idcardno or "").strip().lower(): s
        for s in StudentProfile.objects.exclude(Idcardno__isnull=True).exclude(Idcardno="").only(
            "id", "Idcardno", "parent_id"
        )
    }

    processed = linked = created_users = created_parents = created_students = updated_students = 0
    centre_miss = skipped = 0

    def resolve_user(row: LegacyRow):
        nonlocal created_users
        key = row.idcardno.strip().lower()
        user = users_by_username.get(key)
        if user:
            return user

        if row.email and "@" in row.email:
            user = users_by_email.get(row.email)
            if user:
                return user

        email = row.email if row.email and "@" in row.email else f"parent-{row.idcardno.lower()}@time4kids.local"
        user = User(
            email=email,
            username=row.idcardno[:150],
            full_name=(row.parent_name or row.student_name or row.idcardno)[:255],
            role=UserRole.PARENT.value,
            is_active=True,
        )
        user.set_unusable_password()
        if args.dry_run:
            created_users += 1
            return user

        user.save()
        created_users += 1
        users_by_username[key] = user
        users_by_email[user.email.strip().lower()] = user
        return user

    BATCH = 1000
    pending_parents: list[ParentProfile] = []
    pending_students: list[StudentProfile] = []

    def flush():
        nonlocal pending_parents, pending_students
        if args.dry_run:
            pending_parents = []
            pending_students = []
            return

        with transaction.atomic():
            for pp in pending_parents:
                pp.save()
            for s in pending_students:
                s.save()
        pending_parents = []
        pending_students = []

    for row in parse_legacy_students(args.sql):
        if args.limit and processed >= args.limit:
            break

        processed += 1
        franchise = franchise_for(row.centre)
        if not franchise:
            centre_miss += 1
            continue

        if args.dry_run:
            continue

        user = resolve_user(row)
        linked += 1

        user_updates = []
        if (user.role or "").upper() != UserRole.PARENT.value:
            user.role = UserRole.PARENT.value
            user_updates.append("role")
        if row.idcardno and (user.username or "").strip().lower() != row.idcardno.lower():
            user.username = row.idcardno[:150]
            user_updates.append("username")
        if user_updates and user.pk:
            user.save(update_fields=user_updates)

        pp = parent_by_user_id.get(user.id)
        if pp is None:
            pp = ParentProfile(
                user=user,
                franchise=franchise,
                child_name=row.student_name[:255],
                phone=row.phone,
                city=row.city,
                Emailid=row.email[:254] if row.email and "@" in row.email else None,
            )
            parent_by_user_id[user.id] = pp
            pending_parents.append(pp)
            created_parents += 1
        else:
            changed = False
            if pp.franchise_id != franchise.id:
                pp.franchise = franchise
                changed = True
            if row.student_name and not (pp.child_name or "").strip():
                pp.child_name = row.student_name[:255]
                changed = True
            if row.phone and not (pp.phone or "").strip():
                pp.phone = row.phone
                changed = True
            if changed:
                pending_parents.append(pp)

        id_key = row.idcardno.strip().lower()
        student = students_by_idcard.get(id_key)
        first, last = split_name(row.student_name)

        if student is None:
            student = StudentProfile(
                parent=pp,
                first_name=first,
                last_name=last,
                class_name=row.class_name or "",
                section="",
                roll_number=row.idcardno,
                emergency_contact=row.phone,
                is_active=True,
                State=row.state or None,
                City=row.city or None,
                Centre=row.centre or None,
                Idcardno=row.idcardno,
                Password=row.password or None,
                ParentName=row.parent_name or None,
                Emailid=row.email or None,
                Mobileno=row.phone or None,
                Year=row.year or None,
            )
            students_by_idcard[id_key] = student
            pending_students.append(student)
            created_students += 1
        else:
            changed = False
            if student.parent_id != pp.id:
                student.parent = pp
                changed = True
            for field, value in (
                ("Centre", row.centre or None),
                ("City", row.city or None),
                ("State", row.state or None),
                ("Emailid", row.email or None),
                ("Mobileno", row.phone or None),
                ("Year", row.year or None),
                ("ParentName", row.parent_name or None),
                ("Password", row.password or None),
                ("class_name", row.class_name or ""),
            ):
                if value and getattr(student, field, None) != value:
                    setattr(student, field, value)
                    changed = True
            if changed:
                pending_students.append(student)
                updated_students += 1

        if processed % BATCH == 0:
            flush()
            print(
                f"PROGRESS processed={processed} linked={linked} parents+{created_parents} "
                f"students+{created_students} centre_miss={centre_miss}",
                flush=True,
            )

    flush()

    print(
        "DONE "
        f"processed={processed} linked={linked} created_users={created_users} "
        f"created_parent_profiles={created_parents} created_students={created_students} "
        f"updated_students={updated_students} centre_miss={centre_miss} dry_run={args.dry_run}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
