from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from accounts.models import UserRole
from franchises.models import Franchise, ParentProfile
from students.models import Grade, StudentProfile

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Create a demo StudentProfile (and sample Grade) for a parent user by email. "
        "Use --bootstrap to create the parent user + ParentProfile if missing (needs at least one Franchise in DB)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            default="parent1@example.com",
            help="Parent user email (default: parent1@example.com)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Create another demo student even if one already exists for this parent",
        )
        parser.add_argument(
            "--bootstrap",
            action="store_true",
            help="Create parent User and ParentProfile if missing (local demo; requires a Franchise row)",
        )
        parser.add_argument(
            "--password",
            default="Parent123!",
            help="Password when creating a new parent user via --bootstrap (default: Parent123!)",
        )

    def handle(self, *args, **options):
        email = (options["email"] or "").strip().lower()
        force = options["force"]
        bootstrap = options["bootstrap"]
        bootstrap_password = options["password"] or "Parent123!"

        user = User.objects.filter(email=email).first()
        if not user:
            if not bootstrap:
                self.stderr.write(
                    self.style.ERROR(
                        f'No user with email "{email}". Create the parent first, or re-run with --bootstrap.'
                    )
                )
                return
            user = User.objects.create_user(
                email=email,
                password=bootstrap_password,
                role=UserRole.PARENT,
                full_name="Parent One",
            )
            self.stdout.write(
                self.style.WARNING(
                    f'Created parent user "{email}" (bootstrap). Password: {bootstrap_password}'
                )
            )

        parent_profile = ParentProfile.objects.filter(user=user).first()
        if not parent_profile:
            if not bootstrap:
                self.stderr.write(
                    self.style.ERROR(
                        f'User "{email}" has no ParentProfile. Add them from Franchise / Parents, or use --bootstrap.'
                    )
                )
                return
            franchise = Franchise.objects.order_by("id").first()
            if not franchise:
                self.stderr.write(
                    self.style.ERROR(
                        "No Franchise in database. Create a franchise first, then run again with --bootstrap."
                    )
                )
                return
            parent_profile = ParentProfile.objects.create(
                user=user,
                franchise=franchise,
                child_name="Demo Kid",
                notes="Seeded by seed_demo_student --bootstrap",
            )
            self.stdout.write(
                self.style.WARNING(f'Created ParentProfile linked to franchise "{franchise.name}" (bootstrap).')
            )

        if not force and parent_profile.students.filter(is_active=True).exists():
            self.stdout.write(
                self.style.WARNING(
                    "This parent already has active student(s). Use --force to add another demo child."
                )
            )
            for s in parent_profile.students.filter(is_active=True):
                self.stdout.write(f"  - {s.full_name} ({s.class_name}) id={s.id}")
            return

        student = StudentProfile.objects.create(
            parent=parent_profile,
            first_name="Demo",
            last_name="Kid",
            class_name="KG-2 · Section A",
            roll_number="DK-101",
            is_active=True,
        )

        Grade.objects.create(
            student=student,
            subject="Mathematics",
            exam_type="Term 1",
            marks_obtained=Decimal("85.00"),
            total_marks=Decimal("100.00"),
            grade="A",
            remarks="Sample grade for parent dashboard preview",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Created student "{student.full_name}" (id={student.id}) and one sample grade for {email}.'
            )
        )
        self.stdout.write("Log in as parent and open Student Profile / Marks & Grades to verify.")
