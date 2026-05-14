"""
Simple student password migration: copy plain text from ``StudentProfile.Password``
into ``User.password`` as Django hashes (``make_password``), one ``save()`` per user.

Run from ``time4kidsbe``::

    python manage.py shell -c "exec(open('update_student_passwords_simple.py', encoding='utf-8').read())"

Or::

    python update_student_passwords_simple.py

Skips only when ``user.password`` already starts with ``pbkdf2_``.
"""
from __future__ import annotations

import os

import django
from django.conf import settings

if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "time4kids_be.settings")
    django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password

from students.models import StudentProfile

User = get_user_model()
PROGRESS_EVERY = 1000


def main() -> None:
    updated = 0
    skipped = 0
    missing = 0

    for student in StudentProfile.objects.exclude(Idcardno__isnull=True).exclude(Idcardno="").iterator():
        idcard = (student.Idcardno or "").strip()
        if not idcard:
            continue

        plain = (student.Password or "").strip()
        if not plain:
            continue

        user = User.objects.filter(username=idcard).first()
        if user is None:
            missing += 1
            continue

        current = user.password or ""
        if current.startswith("pbkdf2_"):
            skipped += 1
            continue

        user.password = make_password(plain)
        user.save(update_fields=["password"])
        updated += 1

        if updated % PROGRESS_EVERY == 0:
            print("Updated:", updated)

    print("--- update_student_passwords_simple (done) ---")
    print("Updated:", updated)
    print("Skipped:", skipped)
    print("Missing users:", missing)


main()
