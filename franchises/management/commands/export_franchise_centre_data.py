"""
Export parent + student roster for one centre (for copying local DB → live server).

  python manage.py export_franchise_centre_data domalguda -o domalguda_roster.json
  python manage.py export_franchise_centre_data --franchise-id 123 -o domalguda_roster.json
"""

import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.profile_access import franchise_profile_for_user
from franchises.models import Franchise, ParentProfile
from students.models import StudentProfile

User = get_user_model()


class Command(BaseCommand):
    help = "Export parents and students for one franchise centre to JSON."

    def add_arguments(self, parser):
        parser.add_argument("username", nargs="?", default="", help="Centre login username (e.g. domalguda)")
        parser.add_argument("--franchise-id", type=int, default=0, help="Franchise pk (alternative to username)")
        parser.add_argument("-o", "--output", required=True, help="Output JSON file path")

    def handle(self, *args, **options):
        franchise = self._resolve_franchise(options)
        if not franchise:
            return

        parents = (
            ParentProfile.objects.filter(franchise=franchise)
            .select_related("user")
            .order_by("id")
        )
        students = (
            StudentProfile.objects.filter(parent__franchise=franchise)
            .select_related("parent", "parent__user")
            .order_by("id")
        )

        parent_rows = []
        for pp in parents:
            user = pp.user
            parent_rows.append(
                {
                    "parent_id": pp.id,
                    "username": (user.username or "").strip(),
                    "email": (user.email or "").strip(),
                    "full_name": (user.full_name or "").strip(),
                    "role": user.role,
                    "child_name": (pp.child_name or "").strip(),
                    "phone": (pp.phone or "").strip(),
                    "Emailid": (pp.Emailid or "").strip(),
                    "city": (pp.city or "").strip(),
                }
            )

        student_rows = []
        for st in students:
            parent_user = getattr(getattr(st, "parent", None), "user", None)
            student_rows.append(
                {
                    "student_id": st.id,
                    "parent_username": (parent_user.username or "").strip() if parent_user else "",
                    "parent_email": (parent_user.email or "").strip() if parent_user else "",
                    "first_name": (st.first_name or "").strip(),
                    "last_name": (st.last_name or "").strip(),
                    "class_name": (st.class_name or "").strip(),
                    "section": (st.section or "").strip(),
                    "roll_number": (st.roll_number or "").strip(),
                    "gender": (st.gender or "").strip(),
                    "is_active": bool(st.is_active),
                    "Idcardno": (st.Idcardno or "").strip(),
                    "Centre": (st.Centre or "").strip(),
                    "City": (st.City or "").strip(),
                    "State": (st.State or "").strip(),
                    "ParentName": (st.ParentName or "").strip(),
                    "Emailid": (st.Emailid or "").strip(),
                    "Mobileno": (st.Mobileno or "").strip(),
                    "Year": (st.Year or "").strip(),
                }
            )

        payload = {
            "franchise_id": franchise.id,
            "franchise_slug": franchise.slug,
            "franchise_name": franchise.name,
            "parents_count": len(parent_rows),
            "students_count": len(student_rows),
            "parents": parent_rows,
            "students": student_rows,
        }

        out = Path(options["output"]).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        self.stdout.write(
            self.style.SUCCESS(
                f"Exported franchise {franchise.name!r} (id={franchise.id}): "
                f"{len(parent_rows)} parents, {len(student_rows)} students -> {out}"
            )
        )

    def _resolve_franchise(self, options):
        franchise_id = int(options.get("franchise_id") or 0)
        if franchise_id:
            franchise = Franchise.objects.filter(pk=franchise_id).first()
            if not franchise:
                self.stderr.write(self.style.ERROR(f"No franchise with id={franchise_id}"))
            return franchise

        username = (options.get("username") or "").strip()
        if not username:
            self.stderr.write("Provide a centre username or --franchise-id")
            return None

        user = User.objects.filter(username__iexact=username).first()
        if not user:
            self.stderr.write(self.style.ERROR(f"No user with username {username!r}"))
            return None

        franchise = franchise_profile_for_user(user)
        if not franchise:
            self.stderr.write(self.style.ERROR(f"User {username!r} is not linked to a franchise"))
            return None
        return franchise
