"""
Align ``users.username`` with ``students_studentprofile.Idcardno`` for legacy login.

Run from ``time4kidsbe`` (same folder as ``manage.py``)::

    python manage.py shell -c "exec(open('sync_usernames_from_students.py', encoding='utf-8').read())"

Or::

    python sync_usernames_from_students.py

``python manage.py shell < sync_usernames_from_students.py`` often breaks on multi-line
code with Django's interactive console; prefer the commands above.

Does **not** change ``users.password`` (only ``username``).
"""
from __future__ import annotations

import os

import django
from django.conf import settings

if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "time4kids_be.settings")
    django.setup()

from django.contrib.auth import get_user_model

from students.models import StudentProfile

User = get_user_model()
BATCH_SIZE = 500


def _resolve_user(student: StudentProfile, idcard: str) -> tuple[object | None, str]:
    """
    Match order:
    1. ``User.email`` equals ``student.Emailid`` (case-insensitive), if Emailid set.
    2. ``User.username`` equals ``Idcardno`` (case-insensitive) — already linked row.
    3. ``student.parent.user`` only when this parent has exactly one student profile
       (avoids overwriting parent username for multi-child families).
    """
    email = (student.Emailid or "").strip()

    if email:
        u = User.objects.filter(email__iexact=email).only("id", "username", "email").first()
        if u:
            return u, "email"

    u = User.objects.filter(username__iexact=idcard).only("id", "username", "email").first()
    if u:
        return u, "username"

    if student.parent_id:
        n = StudentProfile.objects.filter(parent_id=student.parent_id).count()
        if n == 1:
            try:
                parent = student.parent
                pu = parent.user
            except Exception:
                return None, ""
            if pu:
                return pu, "parent_single_child"

    return None, ""


def main() -> None:
    updated_total = 0
    skipped_total = 0
    unmatched: list[str] = []
    username_conflicts: list[str] = []
    pending_by_pk: dict[int, object] = {}

    def flush() -> None:
        nonlocal updated_total, pending_by_pk
        if not pending_by_pk:
            return
        batch = list(pending_by_pk.values())
        pending_by_pk.clear()
        User.objects.bulk_update(batch, ["username"])
        updated_total += len(batch)

    qs = StudentProfile.objects.select_related("parent", "parent__user").iterator(chunk_size=1000)

    for student in qs:
        idcard = (student.Idcardno or "").strip()
        if not idcard:
            skipped_total += 1
            continue

        user, how = _resolve_user(student, idcard)
        if user is None:
            unmatched.append(
                f"student_id={student.pk} Idcardno={idcard!r} Emailid={student.Emailid!r} parent_id={student.parent_id}"
            )
            continue

        current = (user.username or "").strip()
        if current == idcard:
            skipped_total += 1
            continue

        other = User.objects.exclude(pk=user.pk).filter(username__iexact=idcard).only("id", "username").first()
        if other:
            username_conflicts.append(
                f"student_id={student.pk} target_username={idcard!r} blocked_by_user_pk={other.pk}"
            )
            skipped_total += 1
            continue

        user.username = idcard
        pending_by_pk[user.pk] = user

        if len(pending_by_pk) >= BATCH_SIZE:
            flush()

    flush()

    print("--- sync_usernames_from_students ---")
    print(f"Updated users: {updated_total}")
    print(f"Skipped (empty Idcardno, already aligned, no match, or conflict): {skipped_total}")
    print(f"Unmatched students (no user resolved): {len(unmatched)}")
    for line in unmatched[:40]:
        print("  ", line)
    if len(unmatched) > 40:
        print(f"  ... and {len(unmatched) - 40} more")
    if username_conflicts:
        print(f"Username conflicts (another user already has this username): {len(username_conflicts)}")
        for line in username_conflicts[:20]:
            print("  ", line)
        if len(username_conflicts) > 20:
            print(f"  ... and {len(username_conflicts) - 20} more")


main()
