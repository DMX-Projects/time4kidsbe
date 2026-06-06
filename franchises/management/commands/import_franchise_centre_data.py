"""
Import parent + student roster JSON (from export_franchise_centre_data) onto this server.

  python manage.py import_franchise_centre_data domalguda_roster.json
  python manage.py import_franchise_centre_data domalguda_roster.json --dry-run
"""

import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import UserRole
from franchises.models import Franchise, ParentProfile
from students.models import StudentProfile

User = get_user_model()


class Command(BaseCommand):
    help = "Import parents and students for one franchise from export_franchise_centre_data JSON."

    def add_arguments(self, parser):
        parser.add_argument("json_file", help="Path to roster JSON from export_franchise_centre_data")
        parser.add_argument("--dry-run", action="store_true", help="Preview counts without writing")
        parser.add_argument(
            "--franchise-id",
            type=int,
            default=0,
            help="Target franchise id on THIS server (default: match by slug from JSON)",
        )

    def handle(self, *args, **options):
        path = Path(options["json_file"]).expanduser()
        if not path.is_file():
            self.stderr.write(self.style.ERROR(f"File not found: {path}"))
            return

        payload = json.loads(path.read_text(encoding="utf-8"))
        franchise = self._resolve_target_franchise(payload, options)
        if not franchise:
            return

        parents_data = payload.get("parents") or []
        students_data = payload.get("students") or []
        dry_run = bool(options.get("dry_run"))

        self.stdout.write(
            f"Target: {franchise.name!r} (id={franchise.id}, slug={franchise.slug})\n"
            f"JSON: {len(parents_data)} parents, {len(students_data)} students"
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no database changes."))
            return

        created_users = updated_users = created_parents = updated_parents = 0
        created_students = updated_students = skipped_students = 0

        parent_by_username: dict[str, ParentProfile] = {}

        with transaction.atomic():
            for row in parents_data:
                username = (row.get("username") or "").strip()
                email = (row.get("email") or "").strip()
                if not username and not email:
                    continue

                user = None
                if username:
                    user = User.objects.filter(username__iexact=username).first()
                if not user and email:
                    user = User.objects.filter(email__iexact=email).first()

                if not user:
                    user = User(
                        username=(username or email)[:150],
                        email=email or f"parent-{username.lower()}@time4kids.local",
                        full_name=(row.get("full_name") or row.get("child_name") or username)[:255],
                        role=UserRole.PARENT.value,
                        is_active=True,
                    )
                    user.set_unusable_password()
                    user.save()
                    created_users += 1
                else:
                    changed = False
                    if row.get("full_name") and not (user.full_name or "").strip():
                        user.full_name = row["full_name"][:255]
                        changed = True
                    if str(user.role or "").upper() != UserRole.PARENT.value:
                        user.role = UserRole.PARENT.value
                        changed = True
                    if changed:
                        user.save(update_fields=["full_name", "role"])
                        updated_users += 1

                pp = ParentProfile.objects.filter(user=user).first()
                if not pp:
                    pp = ParentProfile.objects.create(
                        user=user,
                        franchise=franchise,
                        child_name=(row.get("child_name") or "")[:255],
                        phone=(row.get("phone") or "")[:10],
                        city=(row.get("city") or "")[:100],
                        Emailid=(row.get("Emailid") or None) or None,
                    )
                    created_parents += 1
                else:
                    changed = False
                    if pp.franchise_id != franchise.id:
                        pp.franchise = franchise
                        changed = True
                    for field, key, max_len in (
                        ("child_name", "child_name", 255),
                        ("phone", "phone", 10),
                        ("city", "city", 100),
                    ):
                        val = (row.get(key) or "").strip()
                        if val and not (getattr(pp, field) or "").strip():
                            setattr(pp, field, val[:max_len])
                            changed = True
                    emailid = (row.get("Emailid") or "").strip()
                    if emailid and not (pp.Emailid or "").strip():
                        pp.Emailid = emailid[:254]
                        changed = True
                    if changed:
                        pp.save()
                        updated_parents += 1

                key = (user.username or "").strip().lower()
                if key:
                    parent_by_username[key] = pp
                if email:
                    parent_by_username[email.strip().lower()] = pp

            for row in students_data:
                idcard = (row.get("Idcardno") or row.get("roll_number") or "").strip()
                parent_username = (row.get("parent_username") or "").strip().lower()
                parent_email = (row.get("parent_email") or "").strip().lower()
                pp = parent_by_username.get(parent_username) or parent_by_username.get(parent_email)
                if not pp:
                    skipped_students += 1
                    continue

                student = None
                if idcard:
                    student = StudentProfile.objects.filter(Idcardno__iexact=idcard).first()
                if not student and row.get("roll_number"):
                    student = StudentProfile.objects.filter(roll_number__iexact=row["roll_number"]).first()

                defaults = {
                    "parent": pp,
                    "first_name": (row.get("first_name") or "(no name)")[:100],
                    "last_name": (row.get("last_name") or "")[:100],
                    "class_name": (row.get("class_name") or "")[:50],
                    "section": (row.get("section") or "")[:50],
                    "roll_number": (row.get("roll_number") or idcard or "")[:50],
                    "gender": (row.get("gender") or "")[:1],
                    "is_active": row.get("is_active", True) is not False,
                    "Centre": (row.get("Centre") or franchise.name or None),
                    "City": (row.get("City") or None),
                    "State": (row.get("State") or None),
                    "Idcardno": idcard or None,
                    "ParentName": (row.get("ParentName") or None),
                    "Emailid": (row.get("Emailid") or None),
                    "Mobileno": (row.get("Mobileno") or None),
                    "Year": (row.get("Year") or None),
                }

                if student:
                    changed = False
                    for field, value in defaults.items():
                        if value is not None and value != "" and getattr(student, field) != value:
                            setattr(student, field, value)
                            changed = True
                    if changed:
                        student.save()
                        updated_students += 1
                else:
                    StudentProfile.objects.create(**defaults)
                    created_students += 1

        pc = ParentProfile.objects.filter(franchise=franchise).count()
        sc = StudentProfile.objects.filter(parent__franchise=franchise).count()
        self.stdout.write(
            self.style.SUCCESS(
                "DONE "
                f"users+{created_users} users~{updated_users} "
                f"parents+{created_parents} parents~{updated_parents} "
                f"students+{created_students} students~{updated_students} "
                f"skipped_students={skipped_students}\n"
                f"Now on this server: parents={pc} students={sc} for franchise id={franchise.id}"
            )
        )

    def _resolve_target_franchise(self, payload, options):
        franchise_id = int(options.get("franchise_id") or 0)
        if franchise_id:
            franchise = Franchise.objects.filter(pk=franchise_id).first()
            if not franchise:
                self.stderr.write(self.style.ERROR(f"No franchise with id={franchise_id} on this server"))
            return franchise

        slug = (payload.get("franchise_slug") or "").strip()
        if slug:
            franchise = Franchise.objects.filter(slug=slug).first()
            if franchise:
                return franchise

        name = (payload.get("franchise_name") or "").strip()
        if name:
            matches = list(Franchise.objects.filter(name__iexact=name)[:2])
            if len(matches) == 1:
                return matches[0]

        self.stderr.write(
            self.style.ERROR(
                "Could not match franchise on this server. Use --franchise-id 123 or ensure slug exists."
            )
        )
        return None
