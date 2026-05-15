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


def driver_profile_for_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    try:
        return user.driver_profile
    except ObjectDoesNotExist:
        return None
