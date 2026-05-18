"""City/state helpers derived from active ``Franchise`` rows (not ``FranchiseLocation``)."""

from __future__ import annotations

from collections import Counter, defaultdict

from django.db.models import Q

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
    q = Q()
    for value in expand_state_filter(state_param):
        q |= Q(state__iexact=value)
        q |= Q(state__icontains=value)
    return q


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
        Franchise.objects.filter(is_active=True)
        .exclude(Q(city__isnull=True) | Q(city__exact=""))
        .only("city", "state")
    )
    groups: dict[str, list[Franchise]] = defaultdict(list)
    for row in qs:
        key = _clean(row.city).lower()
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
    """State dropdown options: only states that have at least one active centre."""
    raw_states = (
        Franchise.objects.filter(is_active=True)
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
