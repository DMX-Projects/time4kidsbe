"""
Class-wise limits for teacher logins on centre Parent App endpoints.

Franchise users pass through unchanged (every helper returns the input / no-op).
A teacher only sees and writes rows for their assigned class at their own centre.
"""

from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from accounts.models import UserRole

_UNSET = object()


def _is_teacher(user) -> bool:
    return str(getattr(user, "role", "") or "").strip().upper() == UserRole.TEACHER.value


def teacher_profile_for_request(request):
    """Active TeacherProfile for the request user, or None (also None for non-teachers)."""
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False) or not _is_teacher(user):
        return None
    cached = getattr(request, "_teacher_profile_cache", _UNSET)
    if cached is not _UNSET:
        return cached
    from accounts.profile_access import teacher_profile_for_user

    tp = teacher_profile_for_user(user)
    if tp is not None and not tp.is_active:
        tp = None
    request._teacher_profile_cache = tp
    return tp


def teacher_class_name(request) -> str | None:
    tp = teacher_profile_for_request(request)
    return tp.class_name if tp else None


def teacher_student_ids(request) -> list[int]:
    """Active students at the teacher's centre whose class matches the teacher's class."""
    tp = teacher_profile_for_request(request)
    if tp is None:
        return []
    cached = getattr(request, "_teacher_student_ids_cache", None)
    if cached is not None:
        return cached
    from students.models import StudentProfile
    from students.portal_views import _class_label_matches

    ids = [
        pk
        for pk, class_name in StudentProfile.objects.filter(
            parent__franchise=tp.franchise, is_active=True
        ).values_list("id", "class_name")
        if _class_label_matches(class_name, tp.class_name)
    ]
    request._teacher_student_ids_cache = ids
    return ids


def _matching_class_names(qs, class_name: str) -> list[str]:
    from students.portal_views import _class_label_matches

    names = {class_name}
    for value in qs.order_by().values_list("class_name", flat=True).distinct():
        if value and _class_label_matches(value, class_name):
            names.add(value)
    return list(names)


def scope_class_content(qs, request, *, has_student: bool = True):
    """Homework / notifications / activities / events: rows aimed at the teacher's class (or its students)."""
    tp = teacher_profile_for_request(request)
    if tp is None:
        return qs
    cond = Q(class_name__in=_matching_class_names(qs, tp.class_name))
    if has_student:
        cond |= Q(student_id__in=teacher_student_ids(request) or [-1])
    return qs.filter(cond)


def scope_student_rows(qs, request, field: str = "student_id"):
    """Attendance / grades / students: only rows for the teacher's class students."""
    if teacher_profile_for_request(request) is None:
        return qs
    return qs.filter(**{f"{field}__in": teacher_student_ids(request) or [-1]})


def assert_student_in_teacher_class(request, student) -> None:
    if student is None or teacher_profile_for_request(request) is None:
        return
    if student.pk not in set(teacher_student_ids(request)):
        raise PermissionDenied("This student is not in your class.")


def teacher_class_save_kwargs(request, validated_data) -> dict:
    """Extra ``serializer.save()`` kwargs that pin teacher-created content to their class."""
    tp = teacher_profile_for_request(request)
    if tp is None:
        return {}
    assert_student_in_teacher_class(request, validated_data.get("student"))
    return {"class_name": tp.class_name}
