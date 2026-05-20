"""City/state helpers derived from active ``Franchise`` rows (not ``FranchiseLocation``)."""

from __future__ import annotations

from collections import Counter, defaultdict

from django.db.models import Case, IntegerField, Q, Value, When
from django.db.models.functions import Trim

from .models import Franchise, FranchiseLocation

STATE_CODE_TO_NAME: dict[str, str] = dict(FranchiseLocation.STATE_CHOICES)
STATE_NAME_TO_CODE: dict[str, str] = {
    name.strip().lower(): code for code, name in FranchiseLocation.STATE_CHOICES
}
# Common aliases stored in legacy franchise rows
_STATE_ALIASES: dict[str, str] = {
    "bangalore": "KA",
    "bengaluru": "KA",
    "andhra pradesh": "AP",
    "telangana": "TG",
    "tamil nadu": "TN",
    "west bengal": "WB",
    "madhya pradesh": "MP",
    "uttar pradesh": "UP",
    "himachal pradesh": "HP",
    "jammu and kashmir": "JK",
    "odisha": "OR",
    "orissa": "OR",
    "pondicherry": "PY",
    "puducherry": "PY",
}


def _clean(value: str | None) -> str:
    return (value or "").strip()


def state_to_code(raw: str | None) -> str | None:
    """Map franchise.state (code, full name, or alias) to a 2-letter state code."""
    s = _clean(raw)
    if not s:
        return None
    upper = s.upper()
    if len(upper) == 2 and upper in STATE_CODE_TO_NAME:
        return upper
    lower = s.lower()
    if lower in STATE_NAME_TO_CODE:
        return STATE_NAME_TO_CODE[lower]
    if lower in _STATE_ALIASES:
        return _STATE_ALIASES[lower]
    return None


def state_to_display(raw: str | None) -> str:
    code = state_to_code(raw)
    if code:
        return STATE_CODE_TO_NAME.get(code, _clean(raw))
    return _clean(raw)


def expand_state_filter(state_param: str) -> list[str]:
    """Values to match against ``Franchise.state`` (code, full name, partial)."""
    s = _clean(state_param)
    if not s:
        return []
    variants: set[str] = {s}
    code = state_to_code(s)
    if code:
        variants.add(code)
        variants.add(STATE_CODE_TO_NAME.get(code, ""))
    else:
        for c, name in STATE_CODE_TO_NAME.items():
            if name.lower() == s.lower() or c.lower() == s.lower():
                variants.add(c)
                variants.add(name)
    return [v for v in variants if v]


def state_filter_q(state_param: str) -> Q:
    """Deprecated: use ``filter_queryset_by_state`` (trim-aware)."""
    q = Q()
    for value in expand_state_filter(state_param):
        q |= Q(state__iexact=value)
        q |= Q(state__icontains=value)
    return q


def filter_queryset_by_state(queryset, state_param: str | None):
    """
    Match centres by state using trimmed DB values and all legacy spellings
    that map to the same state code (fixes count vs list mismatches).
    """
    variants = expand_state_filter(state_param)
    target_code = state_to_code(state_param)
    if not variants and not target_code:
        return queryset

    q = Q()
    for value in variants:
        q |= Q(state_trim__iexact=value)

    if target_code:
        for raw in Franchise.objects.values_list("state", flat=True).distinct():
            if not raw:
                continue
            if state_to_code(str(raw)) == target_code:
                trimmed = _clean(str(raw))
                if trimmed:
                    q |= Q(state_trim__iexact=trimmed)

    return queryset.annotate(state_trim=Trim("state")).filter(q)


def normalized_city_key(raw: str | None) -> str:
    return _clean(raw).lower()


# Legacy landing URLs and ads often use colloquial names; franchise.city uses canonical spellings.
_CITY_QUERY_EQUIVALENTS: dict[str, tuple[str, ...]] = {
    "bengaluru": ("bengaluru", "bangalore"),
    "bangalore": ("bengaluru", "bangalore"),
    "mysore": ("mysore", "mysuru"),
    "mysuru": ("mysore", "mysuru"),
}


def city_query_variants(city_param: str | None) -> list[str]:
    """Spellings to match for a public ``?city=`` filter (case-insensitive per variant)."""
    key = normalized_city_key(city_param)
    if not key:
        return []
    group = _CITY_QUERY_EQUIVALENTS.get(key)
    if group:
        return list(group)
    return [key]


def filter_queryset_by_city(queryset, city_param: str | None):
    """Match franchise rows by trimmed, case-insensitive city name (with legacy aliases)."""
    variants = city_query_variants(city_param)
    if not variants:
        return queryset
    q = Q()
    for variant in variants:
        q |= Q(city_trim__iexact=variant)
    return queryset.annotate(city_trim=Trim("city")).filter(q)


def _search_matches_known_city(queryset, term: str) -> bool:
    """True when ``term`` is an exact city name stored on at least one centre."""
    variants = city_query_variants(term)
    if not variants:
        return False
    qs = queryset.annotate(city_trim=Trim("city"))
    for variant in variants:
        if qs.filter(city_trim__iexact=variant).exists():
            return True
    return False


def filter_queryset_by_search(queryset, search_param: str):
    """
    Locate-centre search.

    If the term is a known city name, return only centres in that city (avoids
    false matches from addresses in other cities that mention the name).
    Otherwise search name, city, and address.
    """
    term = _clean(search_param)
    if not term:
        return queryset

    if _search_matches_known_city(queryset, term):
        return filter_queryset_by_city(queryset, term).order_by("name")

    return (
        queryset.filter(
            Q(name__icontains=term) | Q(city__icontains=term) | Q(address__icontains=term)
        )
        .annotate(
            relevance=Case(
                When(name__iexact=term, then=Value(4)),
                When(name__icontains=term, then=Value(3)),
                When(city__icontains=term, then=Value(2)),
                When(address__icontains=term, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("-relevance", "city", "name")
    )


def _pick_display_city(rows: list[Franchise]) -> str:
    names = [_clean(r.city) for r in rows if _clean(r.city)]
    if not names:
        return ""
    return Counter(names).most_common(1)[0][0]


def _pick_display_state_raw(rows: list[Franchise]) -> str:
    states = [_clean(r.state) for r in rows if _clean(r.state)]
    if not states:
        return ""
    return Counter(states).most_common(1)[0][0]


def cities_from_franchises() -> list[dict]:
    """
  Distinct cities with centre counts from ``franchise`` table.
  Used by public/admin location lists and locate-centre dropdowns.
    """
    qs = (
        Franchise.objects.all()
        .exclude(Q(city__isnull=True) | Q(city__exact=""))
        .only("city", "state")
    )
    groups: dict[str, list[Franchise]] = defaultdict(list)
    for row in qs:
        key = normalized_city_key(row.city)
        if key:
            groups[key].append(row)

    locations: list[dict] = []
    for city_key in sorted(groups.keys()):
        rows = groups[city_key]
        city_name = _pick_display_city(rows)
        state_raw = _pick_display_state_raw(rows)
        code = state_to_code(state_raw)
        state_display = state_to_display(state_raw)
        locations.append(
            {
                "id": city_key,
                "city_name": city_name,
                "city": city_name,
                "state": code or state_raw,
                "state_display": state_display,
                "landmark_name": city_name,
                "landmark_type": "fort_generic",
                "is_active": True,
                "display_order": 0,
                "franchise_count": len(rows),
            }
        )

    locations.sort(key=lambda loc: (loc["state_display"].lower(), loc["city_name"].lower()))
    return locations


def state_choices_from_franchises() -> list[dict]:
    """State dropdown options: only states that have at least one centre."""
    raw_states = (
        Franchise.objects.all()
        .exclude(Q(state__isnull=True) | Q(state__exact=""))
        .values_list("state", flat=True)
        .distinct()
    )
    seen: set[str] = set()
    out: list[dict] = []
    for raw in raw_states:
        code = state_to_code(str(raw))
        name = state_to_display(str(raw))
        key = code or name.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append({"code": code or name, "name": name})
    out.sort(key=lambda row: row["name"].lower())
    return out
