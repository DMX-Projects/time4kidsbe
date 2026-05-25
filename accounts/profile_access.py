"""Safe access to reverse OneToOne profiles (franchise / parent).

getattr(user, "franchise_profile", None) is NOT safe: Django's ReverseOneToOneDescriptor
still raises RelatedObjectDoesNotExist when the related row is missing.
"""

from django.core.exceptions import ObjectDoesNotExist

from accounts.models import UserRole


def _norm_role(user) -> str:
    return str(getattr(user, "role", "") or "").strip().upper()


def franchise_slug_login_key(slug: str) -> str:
    """First segment of a centre slug (e.g. ``kondapur`` from ``kondapur-timekids...``)."""
    s = (slug or "").strip().lower()
    if "-timekid" in s:
        s = s.split("-timekid", 1)[0]
    return s.split("-")[0] if s else ""


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

    username = (getattr(user, "username", None) or "").strip()
    if not username:
        return None
    key = username.lower()

    for prefix in (f"{key}-timekid", f"{key}-"):
        match = Franchise.objects.filter(slug__istartswith=prefix).order_by("id").first()
        if match:
            return match

    candidates = list(Franchise.objects.filter(slug__icontains=key).only("id", "slug")[:40])
    matches = [f for f in candidates if franchise_slug_login_key(f.slug) == key]
    if len(matches) == 1:
        return matches[0]
    return None


def franchise_profile_for_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    try:
        return user.franchise_profile
    except ObjectDoesNotExist:
        pass

    from franchises.models import Franchise

    franchise = Franchise.objects.filter(user_id=user.pk).first()
    if franchise:
        return franchise

    return franchise_for_centre_login(user)


def parent_profile_for_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    try:
        return user.parent_profile
    except ObjectDoesNotExist:
        return None


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

    ident = (getattr(user, "username", None) or "").strip()
    if ident:
        student = (
            StudentProfile.objects.filter(Idcardno__iexact=ident)
            .select_related("parent", "parent__franchise")
            .first()
        )
        if student:
            return student, student.parent if student.parent_id else pp

    email = (getattr(user, "email", None) or "").strip()
    if email:
        student = (
            StudentProfile.objects.filter(Emailid__iexact=email)
            .select_related("parent", "parent__franchise")
            .first()
        )
        if student:
            return student, student.parent if student.parent_id else pp

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
        return None
