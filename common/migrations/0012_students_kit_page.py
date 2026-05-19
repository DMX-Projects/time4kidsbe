from django.db import migrations, models


SEED_PAGES = [
    {
        "slug": "nursery",
        "title": "Nursery — Students kit for Academic Year 2026-27",
        "short_label": "Nursery",
        "public_path": "/StudentskitNursery",
        "image_alt": "T.I.M.E. Kids Nursery students kit checklist AY 2026-27",
        "link_label": "Nursery Students Kit AY 2026-27",
        "row_key": "students-kit-nursery-2026-27",
        "order": 0,
    },
    {
        "slug": "play-group",
        "title": "Play Group — Students kit for Academic Year 2026-27",
        "short_label": "Play Group",
        "public_path": "/StudentskitPlayGroup",
        "image_alt": "T.I.M.E. Kids Play Group students kit checklist AY 2026-27",
        "link_label": "Play Group Students Kit AY 2026-27",
        "row_key": "students-kit-pg-2026-27",
        "order": 1,
    },
    {
        "slug": "pp1",
        "title": "PP-1 — Students kit for Academic Year 2026-27",
        "short_label": "PP-1",
        "public_path": "/StudentskitPP1",
        "image_alt": "T.I.M.E. Kids PP-1 students kit checklist AY 2026-27",
        "link_label": "PP-1 Students Kit AY 2026-27",
        "row_key": "students-kit-pp1-2026-27",
        "order": 2,
    },
    {
        "slug": "pp2",
        "title": "PP-2 — Students kit for Academic Year 2026-27",
        "short_label": "PP-2",
        "public_path": "/StudentskitPP2",
        "image_alt": "T.I.M.E. Kids PP-2 students kit checklist AY 2026-27",
        "link_label": "PP-2 Students Kit AY 2026-27",
        "row_key": "students-kit-pp2-2026-27",
        "order": 3,
    },
]


def seed_students_kit_pages(apps, schema_editor):
    StudentsKitPage = apps.get_model("common", "StudentsKitPage")
    for row in SEED_PAGES:
        StudentsKitPage.objects.update_or_create(slug=row["slug"], defaults=row)


def unseed_students_kit_pages(apps, schema_editor):
    StudentsKitPage = apps.get_model("common", "StudentsKitPage")
    StudentsKitPage.objects.filter(slug__in=[r["slug"] for r in SEED_PAGES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0011_seed_franchisee_home_testimonials"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudentsKitPage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(help_text="Programme key: nursery, play-group, pp1, pp2", max_length=32, unique=True)),
                ("title", models.CharField(max_length=255)),
                ("short_label", models.CharField(max_length=64)),
                ("public_path", models.CharField(help_text="Legacy public URL path, e.g. /StudentskitNursery", max_length=64)),
                ("image_alt", models.CharField(blank=True, max_length=255)),
                ("link_label", models.CharField(help_text="Label on franchise Center Page checklist", max_length=255)),
                ("row_key", models.CharField(help_text="Stable key for FranchiseDocument.source_path sync", max_length=64, unique=True)),
                ("academic_year", models.CharField(blank=True, default="AY 2026-27", max_length=32)),
                ("image", models.ImageField(blank=True, upload_to="students_kit_pages/")),
                ("pdf", models.FileField(blank=True, upload_to="students_kit_pages/pdf/")),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Students kit page",
                "verbose_name_plural": "Students kit pages",
                "ordering": ["order", "slug"],
            },
        ),
        migrations.RunPython(seed_students_kit_pages, unseed_students_kit_pages),
    ]
