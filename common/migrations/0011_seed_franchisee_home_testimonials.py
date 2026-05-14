# Seed franchisee quotes for the home page — copy aligned with legacy timekids PHP homepage
# (Franchisee's Speak). Skips if any franchisee row already exists.

from django.db import migrations


def seed_franchisee_testimonials(apps, schema_editor):
    HomeTestimonial = apps.get_model("common", "HomeTestimonial")
    if HomeTestimonial.objects.filter(category="franchisee").exists():
        return
    rows = [
        {
            "category": "franchisee",
            "text": (
                "I have been a franchise of T.I.M.E. Kids for last 6 years. Apart from their amazing "
                "curriculum, innovation and values, the most motivating thing is the constant support "
                "from HO with clear goals. Their continuous support to the day to day running of preschool "
                "right from providing artworks for promotions and various celebrations, suggesting vendors "
                "for printing brochures, giving innovative marketing ideas are definitely an easy path to "
                "success. T.I.M.E. Kids make us feel we are all part of the same family. T.I.M.E. Kids family "
                "is constantly growing and being a part of this growth has been a great decision."
            ),
            "author": "Rachna",
            "relation": "Franchisee",
            "location": "T.I.M.E. Kids Domalguda — Hyderabad",
            "rating": 5,
            "order": 10,
            "is_active": True,
        },
        {
            "category": "franchisee",
            "text": (
                "I always wanted to do something on my own and yet not compromise on quality time with my "
                "family. T.I.M.E. Kids franchise opportunity offered me one of the best business ventures. "
                "As a woman and also a mother, I possessed the inherent qualities and skills required to "
                "nurture little minds. Now, I have a safe, comfortable working environment and flexible "
                "working hours. A partnership with a credible preschool brand has definitely fulfilled my "
                "entrepreneurial aspirations!!"
            ),
            "author": "Shibani",
            "relation": "Woman entrepreneur",
            "location": "T.I.M.E. Kids HSR Layout — Bengaluru",
            "rating": 5,
            "order": 11,
            "is_active": True,
        },
        {
            "category": "franchisee",
            "text": (
                "Giving up an IT career to realize my big dream of becoming an entrepreneur was the best "
                "decision taken by me. The organizational support from T.I.M.E. Kids helped me tremendously "
                "in establishing my own business venture. The training given to the franchisee is exhaustive "
                "and their easy to understand manuals covering all aspects of operations are so helpful for "
                "a new entrant in this field. Academic training sessions are so helpful in understanding the "
                "study material and its implementation. Their experts are also available to help out for the "
                "smallest doubt that we may have. For me, definitely there has been no looking back!"
            ),
            "author": "Akanksha",
            "relation": "IT professional",
            "location": "T.I.M.E. Kids Kundhanhalli — Bengaluru",
            "rating": 5,
            "order": 12,
            "is_active": True,
        },
    ]
    for row in rows:
        HomeTestimonial.objects.create(**row)


def unseed_franchisee_testimonials(apps, schema_editor):
    HomeTestimonial = apps.get_model("common", "HomeTestimonial")
    HomeTestimonial.objects.filter(category="franchisee", order__in=(10, 11, 12)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0010_merge_0009_home_testimonial_category_0009_state_city"),
    ]

    operations = [
        migrations.RunPython(seed_franchisee_testimonials, unseed_franchisee_testimonials),
    ]
