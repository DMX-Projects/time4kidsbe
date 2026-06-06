"""
Show which franchise a centre login maps to and how many parents/students exist.

  python manage.py diagnose_franchise_centre domalguda
  python manage.py diagnose_franchise_centre --slug domalguda
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.profile_access import franchise_centre_diagnostics, franchise_profile_for_user
from franchises.models import Franchise, ParentProfile
from students.models import StudentProfile

User = get_user_model()


class Command(BaseCommand):
    help = "Diagnose centre login → franchise mapping and parent/student counts."

    def add_arguments(self, parser):
        parser.add_argument("username", nargs="?", default="", help="Centre login username (e.g. domalguda)")
        parser.add_argument("--slug", default="", help="List all franchises whose slug contains this text")
        parser.add_argument(
            "--announcement",
            type=int,
            default=0,
            help="Show how many parents are targeted for this announcement id",
        )

    def handle(self, *args, **options):
        username = (options["username"] or "").strip()
        slug_q = (options["slug"] or "").strip()

        if slug_q:
            self._print_slug_matches(slug_q)
            return

        if not username:
            self.stderr.write("Provide a username, e.g. python manage.py diagnose_franchise_centre domalguda")
            return

        user = User.objects.filter(username__iexact=username).first()
        if not user:
            self.stderr.write(self.style.ERROR(f"No user with username {username!r}"))
            similar = list(
                User.objects.filter(username__icontains=username[:6]).values_list("username", flat=True)[:10]
            )
            if similar:
                self.stdout.write(f"Similar usernames: {', '.join(similar)}")
            return

        diag = franchise_centre_diagnostics(user)
        franchise = franchise_profile_for_user(user)

        self.stdout.write(self.style.SUCCESS(f"User: {user.username} (id={user.pk}, role={user.role})"))
        self.stdout.write(f"Linked: {diag.get('linked')}")
        self.stdout.write(f"Resolve method: {diag.get('resolve_method')}")
        self.stdout.write(f"Franchise: {diag.get('franchise_name')} (id={diag.get('franchise_id')})")
        self.stdout.write(f"Parents in DB: {diag.get('parents_count')}")
        self.stdout.write(f"Students in DB: {diag.get('students_count')}")
        if diag.get("hint"):
            self.stdout.write(self.style.WARNING(diag["hint"]))

        if franchise:
            self.stdout.write(f"Slug: {franchise.slug}")
            self.stdout.write(f"Franchise.user_id: {franchise.user_id}")

        ann_id = int(options.get("announcement") or 0)
        if ann_id and franchise:
            from students.models import Announcement
            from students.portal_views import parent_profiles_for_announcement

            ann = Announcement.objects.filter(pk=ann_id, franchise=franchise).first()
            if not ann:
                self.stdout.write(self.style.WARNING(f"Announcement id={ann_id} not found for this franchise."))
            else:
                targets = parent_profiles_for_announcement(ann)
                audience = (ann.class_name or "").strip() or (
                    f"student #{ann.student_id}" if ann.student_id else "All parents"
                )
                self.stdout.write(
                    f"Announcement id={ann.id} title={ann.title!r} audience={audience!r} "
                    f"target_parents={targets.count()}"
                )

        if diag.get("parents_count", 0) <= 5:
            self.stdout.write(
                self.style.WARNING(
                    "\nVery few records for this centre. Deploying code does not copy database rows — "
                    "run your parent/student import on THIS server if you expect hundreds of families."
                )
            )

    def _print_slug_matches(self, slug_q: str) -> None:
        self.stdout.write(f"Franchises matching slug {slug_q!r}:\n")
        for f in Franchise.objects.filter(slug__icontains=slug_q).order_by("id"):
            pc = ParentProfile.objects.filter(franchise=f).count()
            sc = StudentProfile.objects.filter(parent__franchise=f).count()
            self.stdout.write(
                f"  id={f.id}  parents={pc}  students={sc}  user_id={f.user_id}  "
                f"name={f.name!r}  slug={f.slug}"
            )
