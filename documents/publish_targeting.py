"""Parent-document publish scope — which centres and parents see a row."""

from __future__ import annotations

from django.db.models import Q

from franchises.models import Franchise

from .models import DocumentCategory, ParentDocument
from .state_utils import franchise_state_code

INDIAN_STATE_CODE_TO_NAME = {
    "AP": "Andhra Pradesh",
    "AR": "Arunachal Pradesh",
    "AS": "Assam",
    "BR": "Bihar",
    "CG": "Chhattisgarh",
    "GA": "Goa",
    "GJ": "Gujarat",
    "HR": "Haryana",
    "HP": "Himachal Pradesh",
    "JH": "Jharkhand",
    "KA": "Karnataka",
    "KL": "Kerala",
    "MP": "Madhya Pradesh",
    "MH": "Maharashtra",
    "MN": "Manipur",
    "ML": "Meghalaya",
    "MZ": "Mizoram",
    "NL": "Nagaland",
    "OD": "Odisha",
    "PB": "Punjab",
    "RJ": "Rajasthan",
    "SK": "Sikkim",
    "TN": "Tamil Nadu",
    "TS": "Telangana",
    "TR": "Tripura",
    "UP": "Uttar Pradesh",
    "UK": "Uttarakhand",
    "WB": "West Bengal",
}


def _franchise_city(franchise: Franchise | None) -> str:
    if not franchise:
        return ""
    return (franchise.city or getattr(franchise, "cityname", None) or "").strip()


def _franchise_state_codes(franchise: Franchise | None) -> set[str]:
    if not franchise:
        return set()
    codes: set[str] = set()
    code = franchise_state_code(franchise)
    if code:
        codes.add(code)
    raw = (franchise.state or getattr(franchise, "statename", None) or "").strip()
    if raw:
        codes.add(raw)
        for c, label in INDIAN_STATE_CODE_TO_NAME.items():
            if label.lower() == raw.lower():
                codes.add(c)
    return codes


def document_matches_franchise(doc: ParentDocument, franchise: Franchise | None) -> bool:
    """True when a centre should see/manage this parent-app document row."""
    if doc.franchise_id:
        return franchise is not None and doc.franchise_id == franchise.id

    if franchise is None:
        return (doc.publish_scope or ParentDocument.PublishScope.PAN_INDIA) == ParentDocument.PublishScope.PAN_INDIA

    scope = (doc.publish_scope or ParentDocument.PublishScope.PAN_INDIA).strip()

    if scope == ParentDocument.PublishScope.PAN_INDIA:
        if doc.category == DocumentCategory.HOLIDAY_LISTS and doc.state:
            return franchise_state_code(franchise) == doc.state
        return True

    if scope == ParentDocument.PublishScope.ONE_CENTRE:
        ids = {int(x) for x in (doc.target_franchise_ids or []) if str(x).isdigit()}
        return franchise.id in ids

    if scope == ParentDocument.PublishScope.FRANCHISES:
        ids = {int(x) for x in (doc.target_franchise_ids or []) if str(x).isdigit()}
        return franchise.id in ids

    if scope == ParentDocument.PublishScope.STATE:
        states = list(doc.target_states or [])
        if doc.state and doc.state not in states:
            states.append(doc.state)
        centre_states = _franchise_state_codes(franchise)
        return bool(centre_states & set(states))

    if scope == ParentDocument.PublishScope.CITY:
        cities = [(c or "").strip().lower() for c in (doc.target_cities or []) if (c or "").strip()]
        if not cities:
            return False
        centre_city = _franchise_city(franchise).lower()
        return bool(centre_city and centre_city in cities)

    return False


def document_matches_parent(doc: ParentDocument, parent_profile, student=None) -> bool:
    """True when a parent login should see this document (centre + optional class filter)."""
    from accounts.profile_access import effective_franchise_for_parent
    from students.models import StudentProfile
    from students.portal_views import _class_label_matches

    franchise = None
    if parent_profile and parent_profile.franchise_id:
        try:
            franchise = parent_profile.franchise
        except Exception:
            franchise = None
    if not franchise and parent_profile:
        franchise = effective_franchise_for_parent(parent_profile)

    if doc.franchise_id:
        if not franchise or doc.franchise_id != franchise.id:
            return False
    elif not document_matches_franchise(doc, franchise):
        return False

    targets = [str(c).strip() for c in (doc.target_class_names or []) if str(c).strip()]
    if not targets:
        return True
    if not parent_profile:
        return False

    if student is not None:
        for target in targets:
            if _class_label_matches(student.class_name, target):
                return True
        return False

    active_children = StudentProfile.objects.filter(parent=parent_profile, is_active=True).only(
        "class_name"
    )
    child_rows = list(active_children)
    if len(child_rows) > 1:
        # No ?student= (common on Android until child picker is wired): show if any child matches.
        for child in child_rows:
            for target in targets:
                if _class_label_matches(child.class_name, target):
                    return True
        return False
    if len(child_rows) == 1:
        for target in targets:
            if _class_label_matches(child_rows[0].class_name, target):
                return True
        return False

    return False


def filter_documents_for_parent(queryset, parent_profile, student=None):
    """Evaluate publish scope + class filter for each row ( queryset is small per parent )."""
    ids = [
        doc.pk
        for doc in queryset
        if document_matches_parent(doc, parent_profile, student=student)
    ]
    return queryset.filter(pk__in=ids)


def filter_documents_for_franchise(queryset, franchise):
    ids = [doc.pk for doc in queryset if document_matches_franchise(doc, franchise)]
    return queryset.filter(pk__in=ids)


def franchise_documents_base_q(franchise: Franchise) -> Q:
    """Rows a franchise user may list: own uploads + head-office rows targeting this centre."""
    return Q(franchise=franchise) | Q(franchise__isnull=True)
