"""Safe access to reverse OneToOne profiles (franchise / parent).

getattr(user, "franchise_profile", None) is NOT safe: Django's ReverseOneToOneDescriptor
still raises RelatedObjectDoesNotExist when the related row is missing.
"""

from django.core.exceptions import ObjectDoesNotExist


def franchise_profile_for_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    try:
        return user.franchise_profile
    except ObjectDoesNotExist:
        return None


def parent_profile_for_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    try:
        return user.parent_profile
    except ObjectDoesNotExist:
        return None
