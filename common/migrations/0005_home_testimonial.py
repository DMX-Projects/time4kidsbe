from django.db import migrations, models


def seed_home_testimonials(apps, schema_editor):
    HomeTestimonial = apps.get_model("common", "HomeTestimonial")
    if HomeTestimonial.objects.exists():
        return
    rows = [
        {
            "text": "A good school plays an important role in the development of a child. It's the light that helps us choose the right path. I am glad that I found T.I.M.E. Kids for my daughter. In just three months there has been a lot of development in Nandika.",
            "author": "Roma Majumdar",
            "relation": "Mother of Nandika",
            "location": "HYDERABAD",
            "rating": 5,
            "order": 0,
            "is_active": True,
        },
        {
            "text": "T.I.M.E. Kids is my son's second home. It is a completely safe environment. He is playing, learning and enjoying every minute he spends there. Mugil has become a keen learner and is learning new things every day.",
            "author": "Mother of Mugil",
            "relation": "Parent",
            "location": "HYDERABAD",
            "rating": 5,
            "order": 1,
            "is_active": True,
        },
        {
            "text": "T.I.M.E. Kids pre-schools, is one of the most friendly places for toddlers. My kid wants to go to school on Sunday too! The learning is done in such a fun way....",
            "author": "Deepa Bahukhandi",
            "relation": "Mother of Diya",
            "location": "HYDERABAD",
            "rating": 5,
            "order": 2,
            "is_active": True,
        },
        {
            "text": "We have seen amazing growth in our child's confidence. The activities are engaging and the staff is very caring. Highly recommended!",
            "author": "Priya Sharma",
            "relation": "Mother of Aarav",
            "location": "HYDERABAD",
            "rating": 5,
            "order": 3,
            "is_active": True,
        },
    ]
    for row in rows:
        HomeTestimonial.objects.create(**row)


def unseed_home_testimonials(apps, schema_editor):
    HomeTestimonial = apps.get_model("common", "HomeTestimonial")
    HomeTestimonial.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0004_alter_holiday_state"),
    ]

    operations = [
        migrations.CreateModel(
            name="HomeTestimonial",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.TextField()),
                ("author", models.CharField(max_length=200)),
                ("relation", models.CharField(blank=True, max_length=200)),
                ("location", models.CharField(blank=True, max_length=200)),
                ("rating", models.PositiveSmallIntegerField(default=5)),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Home testimonial",
                "verbose_name_plural": "Home testimonials",
                "ordering": ["order", "id"],
            },
        ),
        migrations.RunPython(seed_home_testimonials, unseed_home_testimonials),
    ]
