"""
Migrate passwords from ``students_studentprofile.Password`` into ``users.password``
using Django's ``make_password``.

**Who gets updated**

* Match ``users.username`` to ``students_studentprofile.Idcardno`` (trimmed).
* Student ``Password`` must be non-empty (trimmed).
* **Only** rows where ``users.password`` already looks like Django's default PBKDF2
  format are skipped: prefix ``pbkdf2_`` (case-insensitive). Examples **not** skipped
  and therefore **re-hashed**: bare MD5/SHA1 hex (e.g. ``e76ae395ffe2b2e09930ea6f564f91``),
  ``md5$...``, ``sha1$...``, ``crypt$...``, ``argon2$...``, etc.

Run from ``time4kidsbe``::

    python manage.py shell -c "exec(open('update_student_passwords.py', encoding='utf-8').read())"

Or::

    python update_student_passwords.py

``python manage.py shell < update_student_passwords.py`` is unreliable for multi-line
scripts in the interactive shell; prefer the commands above.
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
BATCH_SIZE = 500


def _already_django_pbkdf2(encoded: str) -> bool:
    """True only for Django PBKDF2 hashes (e.g. pbkdf2_sha256$...). Do not treat MD5/SHA1 hex as Django."""
    s = (encoded or "").strip()
    return bool(s) and s.lower().startswith("pbkdf2_")


def main() -> None:
    updated_total = 0
    skipped_users = 0
    skipped_empty_student_password = 0
    missing_idcardnos: list[str] = []
    pending_by_pk: dict[int, object] = {}

    def flush_batch() -> None:
        nonlocal updated_total, pending_by_pk
        if not pending_by_pk:
            return
        batch = list(pending_by_pk.values())
        pending_by_pk.clear()
        User.objects.bulk_update(batch, ["password"])
        updated_total += len(batch)

    for student in (
        StudentProfile.objects.exclude(Idcardno__isnull=True)
        .exclude(Idcardno="")
        .only("Idcardno", "Password")
        .iterator(chunk_size=1000)
    ):
        idcard = (student.Idcardno or "").strip()
        if not idcard:
            continue

        plain = (student.Password or "").strip()
        if not plain:
            skipped_empty_student_password += 1
            continue

        user = User.objects.filter(username=idcard).only("id", "username", "password").first()
        if user is None:
            missing_idcardnos.append(idcard)
            continue

        current = user.password or ""
        if _already_django_pbkdf2(current):
            skipped_users += 1
            continue

        user.password = make_password(plain)
        pending_by_pk[user.pk] = user

        if len(pending_by_pk) >= BATCH_SIZE:
            flush_batch()

    flush_batch()

    missing_unique = sorted(set(missing_idcardnos))

    print("--- update_student_passwords ---")
    print(f"Updated users: {updated_total}")
    print(f"Skipped users: {skipped_users}")
    print(f"Unmatched usernames: {len(missing_unique)}")
    if skipped_empty_student_password:
        print(
            f"(Student rows skipped — empty/null Password: {skipped_empty_student_password})"
        )
    if missing_unique:
        preview = missing_unique[:50]
        print(f"  Sample unmatched Idcardno: {preview!r}")
        if len(missing_unique) > 50:
            print(f"  ... and {len(missing_unique) - 50} more")


main()
