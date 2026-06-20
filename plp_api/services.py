"""PLP / TiKES push enrollment — create users + parent + student profiles."""

from __future__ import annotations

import re
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from accounts.models import UserRole
from accounts.profile_access import _franchise_for_student_centre
from franchises.models import ParentProfile
from students.models import StudentProfile

User = get_user_model()

# Legacy MySQL ``um_users.group_id`` for parent accounts (see reconcile_users_from_um_users.py).
PARENT_GROUP_ID = 6


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _norm_email(value: Any) -> str:
    return _norm(value).lower()


def _phone10(value: Any) -> str:
    digits = re.sub(r"\D", "", _norm(value))
    if len(digits) >= 10:
        return digits[-10:]
    return ""


def _split_student_name(student_name: str) -> tuple[str, str]:
    parts = student_name.split()
    if not parts:
        return "Student", ""
    first = parts[0][:100]
    last = (" ".join(parts[1:]))[:100] if len(parts) > 1 else ""
    return first, last


def _synthetic_email(username: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", username) or "parent"
    return f"{safe.lower()}@tikes.enrolled.local"


def find_franchise_for_centre(centre: str):
    return _franchise_for_student_centre(centre)


def upsert_plp_user(
    *,
    username: str,
    password: str,
    email: str,
    code: str = "",
    full_name: str = "",
) -> tuple[User, bool]:
    """
    Create or update a parent ``users`` row.

    Matches existing users by username (case-insensitive) then email.
    Returns ``(user, created)``.
    """
    username = _norm(username)
    password = _norm(password)
    email = _norm_email(email) or _synthetic_email(username)
    full_name = _norm(full_name) or username
    code = _norm(code)

    if not username:
        raise ValueError("username is required")
    if not password:
        raise ValueError("password is required")

    user = User.objects.filter(username__iexact=username).first()
    if user is None and email:
        user = User.objects.filter(email__iexact=email).first()

    created = user is None
    if created:
        user = User(
            username=username,
            email=User.objects.normalize_email(email),
            full_name=full_name[:255],
            role=UserRole.PARENT,
            group_id=PARENT_GROUP_ID,
            code=code or None,
            is_active=True,
            is_staff=False,
            is_superuser=False,
            date_joined=timezone.now(),
        )
    else:
        if username and (user.username or "").lower() != username.lower():
            conflict = User.objects.exclude(pk=user.pk).filter(username__iexact=username).exists()
            if conflict:
                raise ValueError(f"username {username!r} is already used by another account")
            user.username = username

    if code:
        user.code = code
    if full_name:
        user.full_name = full_name[:255]
    if email and created:
        user.email = User.objects.normalize_email(email)

    user.role = UserRole.PARENT
    user.is_active = True
    user.set_password(password)
    user.save()
    return user, created


def upsert_student_enrollment(
    user: User,
    *,
    state: str = "",
    city: str = "",
    centre: str = "",
    studentname: str = "",
    class_name: str = "",
    idcardno: str = "",
    password: str = "",
    batch_num: int = 1,
    parentname: str = "",
    emailid: str = "",
    mobileno: str = "",
    year: str = "",
) -> tuple[StudentProfile, ParentProfile, bool, bool]:
    """
    Link ``user`` to a centre and student row.

    Returns ``(student, parent_profile, student_created, parent_created)``.
    """
    idcardno = _norm(idcardno) or _norm(user.username)
    centre = _norm(centre)
    studentname = _norm(studentname)
    class_name = _norm(class_name)
    parentname = _norm(parentname) or _norm(user.full_name)
    emailid = _norm_email(emailid) or _norm_email(user.email)
    phone = _phone10(mobileno)
    plain_password = _norm(password)

    if not idcardno:
        raise ValueError("idcardno is required")
    if not centre:
        raise ValueError("centre is required")
    if not studentname:
        raise ValueError("studentname is required")

    franchise = find_franchise_for_centre(centre)
    if franchise is None:
        raise ValueError(f"No franchise matched centre {centre!r}")

    first_name, last_name = _split_student_name(studentname)

    parent_profile = ParentProfile.objects.filter(user=user).first()
    parent_created = parent_profile is None
    if parent_created:
        parent_profile = ParentProfile(
            user=user,
            franchise=franchise,
            child_name=studentname[:255],
        )
    else:
        parent_profile.franchise = franchise
        if studentname:
            parent_profile.child_name = studentname[:255]

    if emailid and "@" in emailid:
        parent_profile.Emailid = emailid[:254]
    if phone:
        parent_profile.phone = phone
    parent_profile.save()

    student = (
        StudentProfile.objects.filter(Idcardno__iexact=idcardno).select_related("parent").first()
    )
    student_created = student is None
    if student_created:
        student = StudentProfile(
            parent=parent_profile,
            first_name=first_name,
            last_name=last_name,
            class_name=class_name[:50] or "—",
            roll_number=idcardno[:50],
            is_active=True,
        )
    else:
        student.parent = parent_profile
        student.first_name = first_name
        student.last_name = last_name
        if class_name:
            student.class_name = class_name[:50]
        student.is_active = True

    student.State = _norm(state)[:255] or student.State
    student.City = _norm(city)[:255] or student.City
    student.Centre = centre[:255]
    student.Idcardno = idcardno[:255]
    if plain_password:
        student.Password = plain_password[:255]
    student.batch_num = str(batch_num) if batch_num is not None else student.batch_num
    student.ParentName = parentname[:255] or student.ParentName
    if emailid:
        student.Emailid = emailid[:254]
    if mobileno:
        student.Mobileno = mobileno[:255]
    if year:
        student.Year = year[:100]
    student.save()

    if user.username != idcardno:
        other = User.objects.exclude(pk=user.pk).filter(username__iexact=idcardno).exists()
        if not other:
            user.username = idcardno
            user.save(update_fields=["username"])

    return student, parent_profile, student_created, parent_created


@transaction.atomic
def enroll_plp_parent(data: dict[str, Any]) -> dict[str, Any]:
    """
    Full TiKES enrollment in one call.

    Accepts fields from both ``create-user`` and ``create-student-details`` payloads.
    """
    username = _norm(data.get("username")) or _norm(data.get("idcardno"))
    password = _norm(data.get("password"))
    email = _norm_email(data.get("email")) or _norm_email(data.get("emailid"))
    code = _norm(data.get("code"))

    user, user_created = upsert_plp_user(
        username=username,
        password=password,
        email=email or _synthetic_email(username),
        code=code,
        full_name=_norm(data.get("full_name")) or _norm(data.get("parentname")),
    )

    student, parent_profile, student_created, parent_created = upsert_student_enrollment(
        user,
        state=_norm(data.get("state")),
        city=_norm(data.get("city")),
        centre=_norm(data.get("centre")),
        studentname=_norm(data.get("studentname")),
        class_name=_norm(data.get("class")),
        idcardno=_norm(data.get("idcardno")) or username,
        password=password,
        batch_num=int(data.get("batch_num", 1) or 1),
        parentname=_norm(data.get("parentname")),
        emailid=_norm(data.get("emailid")) or email,
        mobileno=_norm(data.get("mobileno")),
        year=_norm(data.get("year")),
    )

    return {
        "user_id": user.pk,
        "user_created": user_created,
        "parent_profile_id": parent_profile.pk,
        "parent_created": parent_created,
        "student_id": student.pk,
        "student_created": student_created,
        "franchise_id": parent_profile.franchise_id,
        "franchise_name": parent_profile.franchise.name if parent_profile.franchise_id else "",
        "username": user.username,
        "id_card_no": student.Idcardno,
    }
