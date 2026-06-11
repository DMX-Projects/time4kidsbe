"""Safe access to reverse OneToOne profiles (franchise / parent).

getattr(user, "franchise_profile", None) is NOT safe: Django's ReverseOneToOneDescriptor
still raises RelatedObjectDoesNotExist when the related row is missing.
"""

import re

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.db.models import Q
from django.utils.text import slugify

from accounts.models import UserRole


def _norm_role(user) -> str:
    return str(getattr(user, "role", "") or "").strip().upper()


def franchise_slug_login_key(slug: str) -> str:
    """First segment of a centre slug (e.g. ``kondapur`` from ``kondapur-timekids...``)."""
    s = (slug or "").strip().lower()
    if "-timekid" in s:
        s = s.split("-timekid", 1)[0]
    return s.split("-")[0] if s else ""


def _login_keys_for_franchise_user(user) -> list[str]:
    """Username and email-derived keys used to match a centre slug after login."""
    keys: list[str] = []

    def add(raw: str | None) -> None:
        key = (raw or "").strip().lower()
        if key and key not in keys:
            keys.append(key)

    add(getattr(user, "username", None) or "")

    email = (getattr(user, "email", None) or "").strip().lower()
    if email and "@" in email:
        local = email.split("@", 1)[0]
        add(local)
        if "+" in local:
            after_plus = local.split("+", 1)[1]
            add(after_plus.split(".")[0])

    return keys


def _slug_matches_login_key(slug: str, key: str) -> bool:
    slug_key = franchise_slug_login_key(slug)
    key = (key or "").strip().lower()
    if not slug_key or not key:
        return False
    if slug_key == key:
        return True
    # e.g. username ``padmaraonagar`` vs slug ``padmaraonagarnew-timekids...``
    return slug_key.startswith(key) or key.startswith(slug_key)


def franchise_for_centre_login(user):
    """
    Legacy imports often left ``franchise.user_id`` on HO/admin accounts while centre
    staff sign in with separate ``FRANCHISE`` users (username ≈ centre slug prefix).
    """
    if not user or not getattr(user, "is_authenticated", False):
        return None
    if _norm_role(user) != UserRole.FRANCHISE.value:
        return None

    from franchises.models import Franchise

    keys = _login_keys_for_franchise_user(user)
    if not keys:
        return None

    for key in keys:
        for prefix in (f"{key}-timekid", f"{key}-"):
            match = Franchise.objects.filter(slug__istartswith=prefix).order_by("id").first()
            if match:
                return match

    seen_ids: set[int] = set()
    matches = []
    for key in keys:
        candidates = list(
            Franchise.objects.filter(slug__icontains=key).only("id", "slug").order_by("id")[:40]
        )
        for franchise in candidates:
            if franchise.id in seen_ids:
                continue
            if _slug_matches_login_key(franchise.slug, key):
                seen_ids.add(franchise.id)
                matches.append(franchise)

    if len(matches) == 1:
        return matches[0]
    return None


def franchise_profile_for_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None

    from franchises.models import Franchise

    # Use filter().first() — legacy data may have multiple franchises per user_id.
    franchise = Franchise.objects.filter(user_id=user.pk).order_by("id").first()
    if franchise:
        return franchise

    return franchise_for_centre_login(user)


def franchise_centre_diagnostics(user) -> dict:
    """Help debug live vs local: is this login tied to a centre, and how many rows exist?"""
    from franchises.models import Franchise, ParentProfile
    from students.models import StudentProfile

    if not user or not getattr(user, "is_authenticated", False):
        return {
            "linked": False,
            "resolve_method": None,
            "franchise_id": None,
            "franchise_name": "",
            "parents_count": 0,
            "students_count": 0,
            "hint": "Not authenticated.",
        }

    direct = Franchise.objects.filter(user_id=user.pk).order_by("id").first()
    franchise = direct or franchise_for_centre_login(user)
    if not franchise:
        return {
            "linked": False,
            "resolve_method": None,
            "franchise_id": None,
            "franchise_name": "",
            "parents_count": 0,
            "students_count": 0,
            "hint": (
                "This centre login is not linked to a franchise row. "
                "On the server run: python manage.py link_franchise_centre_logins"
            ),
        }

    resolve_method = "user_id" if direct else "slug_login"
    parents_count = ParentProfile.objects.filter(franchise=franchise).count()
    students_count = StudentProfile.objects.filter(parent__franchise=franchise).count()
    return {
        "linked": True,
        "resolve_method": resolve_method,
        "franchise_id": franchise.id,
        "franchise_name": franchise.name,
        "parents_count": parents_count,
        "students_count": students_count,
        "hint": "",
    }


def _login_identifiers_for_user(user) -> list[str]:
    keys: list[str] = []

    def add(raw: str | None) -> None:
        key = (raw or "").strip()
        if not key:
            return
        if key.lower() not in {k.lower() for k in keys}:
            keys.append(key)

    add(getattr(user, "username", None))
    add(getattr(user, "email", None))
    email = (getattr(user, "email", None) or "").strip()
    if email and "@" in email:
        add(email.split("@", 1)[0])
    return keys


def _student_id_keys(student) -> list[str]:
    """Legacy id-card values stored on ``Idcardno`` and/or ``roll_number``."""
    keys: list[str] = []

    def add(raw: str | None) -> None:
        key = (raw or "").strip()
        if not key:
            return
        if key.lower() not in {k.lower() for k in keys}:
            keys.append(key)

    add(getattr(student, "Idcardno", None))
    add(getattr(student, "roll_number", None))
    return keys


def _identifier_matches_student_id(key: str, student) -> bool:
    needle = (key or "").strip().lower()
    if not needle:
        return False
    return needle in {k.lower() for k in _student_id_keys(student)}


def _student_queryset():
    from students.models import StudentProfile

    return StudentProfile.objects.select_related("parent", "parent__franchise", "parent__user")


def user_owns_legacy_student(user, student) -> bool:
    """True when this login clearly belongs to the imported student row."""
    if not user or not student:
        return False

    username = (getattr(user, "username", None) or "").strip()
    email = (getattr(user, "email", None) or "").strip().lower()
    student_email = (getattr(student, "Emailid", None) or "").strip().lower()
    mobile = re.sub(r"\D", "", (getattr(student, "Mobileno", None) or ""))[-10:]

    if username and _identifier_matches_student_id(username, student):
        return True
    if email and student_email and email == student_email:
        return True
    if student.parent_id:
        parent_email = (getattr(student.parent, "Emailid", None) or "").strip().lower()
        if email and parent_email and email == parent_email:
            return True
        parent_user_email = (
            getattr(getattr(student.parent, "user", None), "email", None) or ""
        ).strip().lower()
        if email and parent_user_email and email == parent_user_email:
            return True
    if mobile and len(mobile) == 10:
        for key in _login_identifiers_for_user(user):
            digits = re.sub(r"\D", "", key)
            if digits.endswith(mobile):
                return True
    return False


def find_student_for_parent_user(user):
    """Best-effort legacy student row for a parent login (id card, email, phone)."""
    if not user:
        return None

    from franchises.models import ParentProfile

    for key in _login_identifiers_for_user(user):
        student = (
            _student_queryset()
            .filter(Q(Idcardno__iexact=key) | Q(roll_number__iexact=key))
            .first()
        )
        if student:
            return student
        if "@" in key:
            student = _student_queryset().filter(Emailid__iexact=key).first()
            if student:
                return student

    for key in _login_identifiers_for_user(user):
        digits = re.sub(r"\D", "", key)
        if len(digits) >= 10:
            phone10 = digits[-10:]
            student = _student_queryset().filter(Mobileno__icontains=phone10).first()
            if student:
                return student

    email = (getattr(user, "email", None) or "").strip()
    if email and "@" in email:
        profile = (
            ParentProfile.objects.filter(Emailid__iexact=email)
            .select_related("franchise", "user")
            .order_by("-id")
            .first()
        )
        if profile:
            student = _student_queryset().filter(parent=profile).order_by("-updated_at", "id").first()
            if student:
                return student

    return None


def _sync_parent_profile_user(profile, user, *, student=None):
    """Attach legacy parent profile to the logged-in user when safe."""
    if not profile or not user:
        return profile
    if profile.user_id == user.pk:
        return profile

    can_claim = False
    if student and user_owns_legacy_student(user, student):
        can_claim = True
    else:
        username = (getattr(user, "username", None) or "").strip()
        email = (getattr(user, "email", None) or "").strip()
        can_claim = _student_queryset().filter(parent=profile).filter(
            Q(Idcardno__iexact=username)
            | Q(roll_number__iexact=username)
            | Q(Emailid__iexact=email)
        ).exists()

    if can_claim or not profile.user_id:
        try:
            profile.user = user
            profile.save(update_fields=["user_id"])
        except IntegrityError:
            pass
    return profile


def parent_profile_for_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None

    from franchises.models import ParentProfile

    student = find_student_for_parent_user(user)
    if student and student.parent_id and user_owns_legacy_student(user, student):
        synced = _sync_parent_profile_user(student.parent, user, student=student)
        if synced:
            return synced

    try:
        profile = user.parent_profile
        if student and student.parent_id and profile.pk != student.parent_id:
            student_franchise = _franchise_for_legacy_student(student)
            profile_franchise_id = profile.franchise_id
            if student_franchise and profile_franchise_id == student_franchise.id:
                student.parent = profile
                student.save(update_fields=["parent_id"])
        return _sync_parent_profile_user(profile, user, student=student)
    except ObjectDoesNotExist:
        pass

    profile = ParentProfile.objects.filter(user_id=user.pk).select_related("franchise", "user").first()
    if profile:
        return profile

    for key in _login_identifiers_for_user(user):
        if "@" not in key:
            continue
        profile = (
            ParentProfile.objects.filter(Emailid__iexact=key)
            .select_related("franchise", "user")
            .order_by("-id")
            .first()
        )
        if profile:
            return _sync_parent_profile_user(profile, user)

    return None


def _franchise_for_student_centre(centre_name: str):
    from franchises.models import Franchise

    centre = (centre_name or "").strip()
    if not centre:
        return None

    franchises = list(Franchise.objects.filter(is_active=True).only("id", "name", "slug"))
    key_slug = slugify(centre).strip().lower()
    if key_slug:
        for franchise in franchises:
            if (franchise.slug or "").strip().lower() == key_slug:
                return franchise
        for franchise in franchises:
            slug = (franchise.slug or "").strip().lower()
            if slug.startswith(f"{key_slug}-") or slug.startswith(f"{key_slug}_"):
                return franchise

    key_name = centre.lower()
    for franchise in franchises:
        if (franchise.name or "").strip().lower() == key_name:
            return franchise

    needle = key_name
    matches = [
        franchise
        for franchise in franchises
        if needle and needle in (franchise.name or "").strip().lower()
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _franchise_for_legacy_student(student):
    """Best-effort franchise for an imported student row."""
    from franchises.models import Franchise

    franchise = _franchise_for_student_centre(student.Centre or "")
    if franchise:
        return franchise

    if student.parent_id:
        try:
            franchise = student.parent.franchise
            if franchise:
                return franchise
        except ObjectDoesNotExist:
            pass

    city = (getattr(student, "City", None) or "").strip()
    if city:
        matches = list(
            Franchise.objects.filter(is_active=True, city__iexact=city).order_by("id")[:2]
        )
        if len(matches) == 1:
            return matches[0]

    return None


def effective_franchise_for_parent(parent_profile):
    """
    Centre used for parent portal content (announcements, homework, events).
    Prefers the enrolled child's centre when ``ParentProfile.franchise`` is missing or stale.
    """
    if not parent_profile:
        return None

    from franchises.models import Franchise, ParentProfile
    from students.models import StudentProfile

    franchise = None
    if parent_profile.franchise_id:
        try:
            franchise = parent_profile.franchise
        except ObjectDoesNotExist:
            franchise = None

    for student in StudentProfile.objects.filter(parent=parent_profile, is_active=True).order_by(
        "-updated_at", "id"
    )[:8]:
        resolved = _franchise_for_legacy_student(student)
        if not resolved:
            continue
        franchise = resolved
        if parent_profile.franchise_id != resolved.id:
            ParentProfile.objects.filter(pk=parent_profile.pk).update(franchise_id=resolved.id)
            parent_profile.franchise_id = resolved.id
        break

    return franchise


def parents_at_franchise(franchise):
    """All parent profiles tied to a centre (profile row and/or enrolled children)."""
    from franchises.models import ParentProfile
    from students.models import StudentProfile

    if not franchise:
        return ParentProfile.objects.none()

    parent_ids = set(
        ParentProfile.objects.filter(franchise=franchise).values_list("pk", flat=True)
    )
    for student in StudentProfile.objects.filter(is_active=True, parent_id__isnull=False).only(
        "parent_id", "Centre", "City"
    ):
        if student.parent_id in parent_ids:
            continue
        if _franchise_for_legacy_student(student) == franchise:
            parent_ids.add(student.parent_id)

    return ParentProfile.objects.filter(pk__in=parent_ids).select_related("user", "franchise")


def ensure_parent_profile_for_user(user):
    """
    Resolve the parent's centre profile for portal actions (tickets, etc.).
    Creates and links a ``ParentProfile`` from legacy ``StudentProfile`` rows when missing.
    """
    profile = parent_profile_for_user(user)
    if profile:
        return profile

    if _norm_role(user) != UserRole.PARENT.value:
        return None

    from franchises.models import ParentProfile

    student = find_student_for_parent_user(user)
    if not student or not user_owns_legacy_student(user, student):
        return None

    if student.parent_id:
        synced = _sync_parent_profile_user(student.parent, user, student=student)
        if synced:
            return synced

    franchise = _franchise_for_legacy_student(student)
    if not franchise:
        return None

    child_name = student.full_name or (student.ParentName or "").strip()
    email = (getattr(user, "email", None) or "").strip()
    student_email = (getattr(student, "Emailid", None) or "").strip()
    profile, _created = ParentProfile.objects.get_or_create(
        user=user,
        defaults={
            "franchise": franchise,
            "child_name": child_name[:255],
            "Emailid": (
                email[:254]
                if email and "@" in email
                else (student_email[:254] if student_email and "@" in student_email else None)
            ),
            "phone": re.sub(r"\D", "", (student.Mobileno or ""))[-10:],
        },
    )
    if not _created and franchise and profile.franchise_id != franchise.id:
        profile.franchise = franchise
        profile.save(update_fields=["franchise_id"])
    if not student.parent_id:
        student.parent = profile
        student.save(update_fields=["parent_id"])
    return profile


def resolved_parent_profile_for_user(user):
    """Parent profile for portal APIs; auto-links legacy student rows when needed."""
    return ensure_parent_profile_for_user(user) or parent_profile_for_user(user)


def primary_student_for_parent_user(user):
    """
    Best-effort student row for a parent login (portal + legacy id-card accounts).
    Returns ``(student, parent_profile)``; either may be ``None``.
    """
    if not user:
        return None, None

    from students.models import StudentProfile

    pp = parent_profile_for_user(user)
    if pp:
        students_qs = (
            StudentProfile.objects.filter(parent=pp, is_active=True)
            .select_related("parent", "parent__franchise")
            .order_by("-updated_at", "id")
        )
        student = (
            students_qs.exclude(Idcardno__isnull=True)
            .exclude(Idcardno="")
            .first()
            or students_qs.first()
        )
        if student:
            return student, pp

    student = find_student_for_parent_user(user)
    if student:
        profile = student.parent if student.parent_id else pp
        return student, profile or pp

    return None, pp


def student_gender_for_login(student) -> tuple[str, str]:
    """Return ``(gender_code, gender_label)`` — e.g. ``("M", "Male")``."""
    if not student:
        return "", ""
    raw = (getattr(student, "gender", None) or "").strip().upper()
    if raw in ("M", "MALE"):
        return "M", "Male"
    if raw in ("F", "FEMALE"):
        return "F", "Female"
    return "", ""


def parent_login_context(user) -> dict:
    """
    Extra fields for parent JWT login / ``/auth/me/`` responses.

    Keys: child_name, franchise, franchise_id, class, id_card_no, academic_year,
    gender, gender_label.
    """
    student, pp = primary_student_for_parent_user(user)

    franchise_name = ""
    franchise_id = None
    if pp and pp.franchise_id:
        try:
            franchise_name = (pp.franchise.name or "").strip()
            franchise_id = pp.franchise.id
        except ObjectDoesNotExist:
            pass
    elif student and (student.Centre or "").strip():
        franchise_name = (student.Centre or "").strip()

    child_name = ""
    if student:
        child_name = student.full_name
    elif pp:
        child_name = (pp.child_name or "").strip()

    class_name = (student.class_name or "").strip() if student else ""
    id_card_no = ""
    if student:
        id_card_no = (student.Idcardno or "").strip()
    if not id_card_no:
        id_card_no = (getattr(user, "username", None) or "").strip()

    academic_year = (student.Year or "").strip() if student else ""
    gender, gender_label = student_gender_for_login(student)

    parent_full_name = ""
    if user:
        parent_full_name = (getattr(user, "full_name", None) or "").strip()

    # App home/header greeting: child name only (not parent full_name).
    display_name = child_name or parent_full_name

    return {
        "child_name": child_name,
        "display_name": display_name,
        "franchise": franchise_name,
        "franchise_id": franchise_id,
        "class": class_name,
        "id_card_no": id_card_no,
        "academic_year": academic_year,
        "gender": gender,
        "gender_label": gender_label,
    }


def driver_profile_for_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    try:
        return user.driver_profile
    except ObjectDoesNotExist:
        pass

    from franchises.models import DriverProfile

    profile = DriverProfile.objects.filter(user_id=user.pk).select_related("user").first()
    if profile:
        return profile

    email = (getattr(user, "email", None) or "").strip()
    if email:
        return (
            DriverProfile.objects.filter(user__email__iexact=email)
            .select_related("user")
            .order_by("-id")
            .first()
        )
    return None
