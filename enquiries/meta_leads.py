"""Meta Lead Ads → TIME Kids CRM helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

from .models import CrmLead, CrmLeadSource, MetaLeadSuppress

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# Cached Page token resolved from a system-user / user token.
_resolved_page_token: str | None = None


# Common Meta Instant Form field names → CRM keys
_FIELD_ALIASES = {
    "full_name": "full_name",
    "full name": "full_name",
    "name": "full_name",
    "email": "email",
    "phone_number": "phone",
    "phone": "phone",
    "mobile": "phone",
    "city": "city",
    "state": "state",
}

# Instant Form tracking / Ads Manager CSV columns (hidden or export metadata).
# CSV values use prefixes: l: lead, ag: ad, as: adset, c: campaign, f: form, p: phone.
_TRACKING_FIELD_ALIASES = {
    "ad_id": "ad_id",
    "adid": "ad_id",
    "adgroup_id": "ad_id",
    "ad_name": "ad_name",
    "adname": "ad_name",
    "adset_id": "adset_id",
    "adsetid": "adset_id",
    "adset_name": "adset_name",
    "adsetname": "adset_name",
    "campaign_id": "campaign_id",
    "campaignid": "campaign_id",
    "campaign_name": "campaign_name",
    "campaignname": "campaign_name",
    "form_id": "form_id",
    "formid": "form_id",
    "form_name": "form_name",
    "formname": "form_name",
    "platform": "platform",
    "is_organic": "is_organic",
    "created_time": "created_time",
    "fbclid": "fbclid",
}

_META_EXPORT_ID_PREFIXES = ("l:", "ag:", "as:", "c:", "f:", "p:")


def _normalize_meta_field_key(name: str) -> str:
    return re.sub(r"[\s.\-]+", "_", str(name or "").strip().lower()).strip("_")


def _is_unresolved_meta_macro(value: str) -> bool:
    text = str(value or "").strip()
    return text.startswith("{{") and text.endswith("}}")


def strip_meta_export_prefix(value: Any) -> str:
    """Strip Ads Manager CSV prefixes: l: / ag: / as: / c: / f: / p:."""
    text = str(value or "").strip().strip('"')
    if not text:
        return ""
    lower = text.lower()
    for prefix in _META_EXPORT_ID_PREFIXES:
        if lower.startswith(prefix):
            return text[len(prefix) :].strip().strip('"')
    return text


def _first_tracking_id(*values: Any) -> str:
    """First real tracking id — skip blanks, {{ad.id}} macros, and CSV prefixes."""
    for value in values:
        text = strip_meta_export_prefix(value)
        if text and not _is_unresolved_meta_macro(text):
            return text
    return ""


def _first_tracking_text(*values: Any) -> str:
    """First non-empty name/label (ad_name, campaign_name, …)."""
    for value in values:
        text = str(value or "").strip().strip('"')
        if text and not _is_unresolved_meta_macro(text):
            return text
    return ""


def meta_page_access_token() -> str:
    return (getattr(settings, "META_PAGE_ACCESS_TOKEN", "") or "").strip()


def meta_webhook_verify_token() -> str:
    return (getattr(settings, "META_WEBHOOK_VERIFY_TOKEN", "") or "").strip()


def meta_app_secret() -> str:
    return (getattr(settings, "META_APP_SECRET", "") or "").strip()


def meta_page_id() -> str:
    configured = (getattr(settings, "META_PAGE_ID", "") or "").strip()
    return configured or "187099544682886"


def meta_leads_sync_since() -> datetime | None:
    """
    Only import Meta Instant Form leads created on/after this moment.

    Set META_LEADS_SYNC_SINCE=YYYY-MM-DD (or full ISO datetime) so auto-sync
    does not keep pulling historical Instant Form leads before campaigns start.
    """
    raw = (
        getattr(settings, "META_LEADS_SYNC_SINCE", None)
        or os.getenv("META_LEADS_SYNC_SINCE")
        or ""
    )
    raw = str(raw).strip()
    if not raw:
        return None
    try:
        # Date-only → start of that day UTC
        if len(raw) <= 10:
            d = datetime.strptime(raw[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return d
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        logger.warning("Invalid META_LEADS_SYNC_SINCE=%r — ignoring cutoff", raw)
        return None


def _parse_meta_created_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        try:
            return datetime.fromtimestamp(int(text), tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def is_before_sync_cutoff(created_time: Any) -> bool:
    """True when lead is older than META_LEADS_SYNC_SINCE (should not import)."""
    since = meta_leads_sync_since()
    if since is None:
        return False
    created = _parse_meta_created_time(created_time)
    if created is None:
        # Without a timestamp, allow webhook/live imports; block only clearly old sync rows.
        return False
    return created < since


# Exact Instant Form names from the campaign sheet.
# Base: 6 states × 8 segments = 48. Kerala R1 adds 8 verified city-dropdown forms.
_BCWW_TK_STATES = (
    "Tamil Nadu",
    "Karnataka",
    "Andhra Pradesh",
    "Kerala",
    "Telangana",
    "Maharashtra",
)
_BCWW_TK_SEGMENTS = (
    "All Interest P1",
    "RMK P1",
    "LLK P1",
    "Income P1",
    "All Interest Ex P1",
    "RMK Ex P1",
    "LLK Ex P1",
    "Income Ex P1",
)
BCWW_TK_KERALA_R1_FORM_NAMES: frozenset[str] = frozenset(
    f"BCWW TK Kerala {segment} - R1" for segment in _BCWW_TK_SEGMENTS
)
# Original sheet names (kept for reference). Default import gate is prefix "BCWW TK".
BCWW_TK_CAMPAIGN_FORM_NAMES: frozenset[str] = frozenset(
    f"BCWW TK {state} {segment}"
    for state in _BCWW_TK_STATES
    for segment in _BCWW_TK_SEGMENTS
) | BCWW_TK_KERALA_R1_FORM_NAMES

# Meta Instant Form city dropdown keys → CRM territory city (matching sheet districts).
# Display label is title-cased from the key when not listed.
_META_CITY_TO_CRM: dict[str, str] = {
    # P1 core cities
    "kochi": "Ernakulam",
    "cochin": "Ernakulam",
    "ernakulam": "Ernakulam",
    "thiruvananthapuram": "Trivandrum",
    "trivandrum": "Trivandrum",
    "kozhikode": "Kozhikode",
    "calicut": "Kozhikode",
    "thrissur": "Thrissur",
    "trichur": "Thrissur",
    "kollam": "Kollam",
    "quilon": "Kollam",
    "kannur": "Kannur",
    "cannanore": "Kannur",
    # Ex / extended towns → district used on CRM sheet
    "pathanamthitta": "Pathanamthitta",
    "alappuzha": "Alappuzha",
    "alleppey": "Alappuzha",
    "kottayam": "Kottayam",
    "idukki": "Idukki",
    "palakkad": "Palakkad",
    "palghat": "Palakkad",
    "malappuram": "Malappuram",
    "pala": "Kottayam",
    "nedumangad": "Trivandrum",
    "kothamangalam": "Ernakulam",
    "kasaragod": "Kasaragod",
    "kasargod": "Kasaragod",
    "kalpetta": "Wayanad",
    "wayanad": "Wayanad",
    "tirur": "Malappuram",
    "perinthalmanna": "Malappuram",
    "ponnani": "Malappuram",
    "nilambur": "Malappuram",
    "vadakara": "Kozhikode",
    "koyilandy": "Kozhikode",
    "feroke": "Kozhikode",
    "guruvayur": "Thrissur",
    "irinjalakuda": "Thrissur",
    "chalakudy": "Thrissur",
    "changanassery": "Kottayam",
    "mavelikkara": "Alappuzha",
    "cherthala": "Alappuzha",
    "kayamkulam": "Alappuzha",
    "neyyattinkara": "Trivandrum",
    "attingal": "Trivandrum",
    "kanhangad": "Kasaragod",
    "taliparamba": "Kannur",
    "payyanur": "Kannur",
    "ottappalam": "Palakkad",
    "shoranur": "Palakkad",
    "adoor": "Pathanamthitta",
    "pandalam": "Pathanamthitta",
    "thodupuzha": "Idukki",
    "muvattupuzha": "Ernakulam",
    "north_paravur": "Ernakulam",
    "north paravur": "Ernakulam",
    "kodungallur": "Thrissur",
    "angamaly": "Ernakulam",
    "mattannur": "Kannur",
    "sulthan_bathery": "Wayanad",
    "sulthan bathery": "Wayanad",
}


def normalize_meta_city(raw: str) -> tuple[str, str]:
    """
    Map Meta Instant Form city dropdown keys to CRM territory cities.

    Returns ``(crm_city, display_label)``.
    ``crm_city`` matches sheet districts (Ernakulam, Trivandrum, …) for assignment.
    ``display_label`` is a readable town/city name for preferred centre / UI.
    """
    text = str(raw or "").strip()
    if not text:
        return "", ""
    key = re.sub(r"\s+", "_", text.strip().lower().replace("-", "_"))
    key_spaced = key.replace("_", " ")
    crm = _META_CITY_TO_CRM.get(key) or _META_CITY_TO_CRM.get(key_spaced) or ""
    # Pretty label from Meta key: north_paravur → North Paravur
    display = re.sub(r"_+", " ", text).strip()
    display = re.sub(r"\s+", " ", display)
    if display.islower() or "_" in text:
        display = display.replace("_", " ").title()
    if not crm:
        # Free-text / unknown: keep cleaned text as both
        return display, display
    return crm, display


def meta_leads_form_id_allowlist() -> set[str]:
    """Optional exact Instant Form IDs (comma-separated META_LEADS_FORM_IDS)."""
    raw = (
        getattr(settings, "META_LEADS_FORM_IDS", None)
        or os.getenv("META_LEADS_FORM_IDS")
        or ""
    )
    return {part.strip() for part in str(raw).split(",") if part.strip()}


def meta_leads_form_name_allowlist() -> set[str] | None:
    """
    Exact form-name allowlist, or None to use name prefixes.

    Default / ``*``: prefix mode — any Instant Form whose name starts with
    ``BCWW TK`` (new campaign revisions like ``… - R2`` capture automatically).
    ``META_LEADS_FORM_NAMES=name1,name2`` → lock to that exact list only.
    """
    raw = getattr(settings, "META_LEADS_FORM_NAMES", None)
    if raw is None:
        raw = os.getenv("META_LEADS_FORM_NAMES")
    text = str(raw or "").strip()
    if not text or text == "*":
        return None
    return {part.strip() for part in text.split(",") if part.strip()}


def meta_leads_form_prefixes() -> list[str]:
    """
    Fallback name-prefix filter when exact allowlist is disabled (*).

    META_LEADS_FORM_PREFIXES=* → allow all form names (IDs allowlist still applies).
    """
    raw = getattr(settings, "META_LEADS_FORM_PREFIXES", None)
    if raw is None:
        raw = os.getenv("META_LEADS_FORM_PREFIXES")
    if raw is None:
        return ["BCWW TK"]
    text = str(raw).strip()
    if not text:
        return ["BCWW TK"]
    if text == "*":
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def is_allowed_meta_form(*, form_id: str = "", form_name: str = "") -> bool:
    """
    Gate Instant Form imports to BCWW TK campaign forms.

    Priority:
    1. META_LEADS_FORM_IDS — exact form ID always allowed.
    2. Exact form-name list, only if META_LEADS_FORM_NAMES is a comma list.
    3. Default: META_LEADS_FORM_PREFIXES (BCWW TK) — new ``BCWW TK …`` forms
       are captured without updating an allowlist.
    """
    form_id = str(form_id or "").strip()
    form_name = str(form_name or "").strip()
    id_allow = meta_leads_form_id_allowlist()
    name_allow = meta_leads_form_name_allowlist()

    if id_allow and form_id and form_id in id_allow:
        return True

    if name_allow is not None:
        if not form_name:
            return False
        return form_name.casefold() in {n.casefold() for n in name_allow}

    # Exact name list disabled — fall back to prefixes / open.
    prefixes = meta_leads_form_prefixes()
    if not prefixes:
        if id_allow:
            return bool(form_id and form_id in id_allow)
        return True
    if not form_name:
        return False
    name_l = form_name.lower()
    return any(name_l.startswith(prefix.lower()) for prefix in prefixes)


def normalize_indian_mobile(raw: str) -> str:
    digits = re.sub(r"\D", "", str(raw or ""))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


def _is_meta_test_value(value: str) -> bool:
    return str(value or "").strip().lower().startswith("<test lead")


def _clean_text(value: str, *, fallback: str = "") -> str:
    text = str(value or "").strip()
    if not text or _is_meta_test_value(text):
        return fallback
    return text


def _format_meta_choice_label(value: str) -> str:
    """Turn Meta Instant Form keys like ``3_months`` into readable month labels.

    Yes/No answers are not valid start periods — return empty for those.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    lower = text.lower().strip("_")
    # Not a timeframe — Instant Form sometimes stores yes/no on this question.
    if lower in {"yes", "no", "y", "n"}:
        return ""
    known = {
        "3_months": "3 months",
        "6_months": "6 months",
        "1_month": "1 month",
        "12_months": "12 months",
        "1_year": "1 year",
        "immediately": "Immediately",
        "asap": "ASAP",
        "test": "Test",
    }
    if text.lower() in known:
        return known[text.lower()]
    if lower in known:
        return known[lower]
    # Keep month/time-like values; drop pure yes/no leftovers.
    pretty = re.sub(r"_+", " ", text).strip(" _-")
    pretty = re.sub(r"\s+", " ", pretty).strip()
    if pretty.lower() in {"yes", "y", "no", "n"}:
        return ""
    if re.search(r"\d+\s*(month|months|year|years|week|weeks|day|days)", pretty, re.I):
        return pretty
    if pretty.lower() in {"immediately", "asap", "test"}:
        return pretty[:1].upper() + pretty[1:].lower() if pretty.lower() != "asap" else "ASAP"
    # Unknown non-month token — hide rather than show yes/no junk
    if re.fullmatch(r"[a-zA-Z]+", pretty) and pretty.lower() not in {"immediately", "asap", "test"}:
        return ""
    return pretty


def format_meta_choice_label(value: str) -> str:
    """Public alias for CRM API display of Instant Form choice values."""
    return _format_meta_choice_label(value)


def verify_meta_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Validate X-Hub-Signature-256 when App Secret is configured."""
    secret = meta_app_secret()
    if not secret:
        # Allow local/dev without secret; production should set META_APP_SECRET.
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = signature_header.split("=", 1)[1].strip()
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, expected)


def _graph_get_with_token(
    path: str,
    token: str,
    params: dict[str, str] | None = None,
) -> dict[str, Any]:
    from urllib.error import HTTPError

    if not token:
        raise RuntimeError("META_PAGE_ACCESS_TOKEN is not configured.")

    query = dict(params or {})
    query["access_token"] = token
    url = f"{GRAPH_BASE}/{path.lstrip('/')}?{urlencode(query)}"
    req = Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        raise RuntimeError(f"Meta Graph {exc.code}: {body or exc.reason}") from exc


def resolve_page_access_token() -> str:
    """
    Prefer a true Page access token.

    System User tokens often need:
      GET /{page-id}?fields=access_token
    before /{page-id}/leadgen_forms will work.
    """
    global _resolved_page_token
    if _resolved_page_token:
        return _resolved_page_token

    configured = meta_page_access_token()
    if not configured:
        raise RuntimeError("META_PAGE_ACCESS_TOKEN is not configured.")

    page_id = meta_page_id()
    try:
        data = _graph_get_with_token(page_id, configured, {"fields": "access_token,name"})
        page_token = str(data.get("access_token") or "").strip()
        if page_token:
            _resolved_page_token = page_token
            logger.info("Resolved Meta Page access token for page_id=%s", page_id)
            return page_token
    except Exception:
        logger.exception("Could not resolve Page token from configured token; using configured token as-is")

    _resolved_page_token = configured
    return configured


def _graph_get(path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    return _graph_get_with_token(path, resolve_page_access_token(), params)


def fetch_lead_by_id(leadgen_id: str) -> dict[str, Any]:
    # Ads Manager CSV uses ad_name / campaign_name / adset_name — request the same fields.
    return _graph_get(
        str(leadgen_id),
        {
            "fields": (
                "id,created_time,ad_id,ad_name,adset_id,adset_name,"
                "campaign_id,campaign_name,form_id,field_data,platform,is_organic"
            )
        },
    )


def fetch_form_name(form_id: str) -> str:
    if not form_id:
        return ""
    try:
        data = _graph_get(str(form_id), {"fields": "name"})
        return str(data.get("name") or "").strip()
    except Exception:
        logger.exception("Failed to fetch Meta form name for form_id=%s", form_id)
        return ""


def _normalize_tracking_param_map(raw: Any) -> dict[str, str]:
    """Normalize Meta tracking_parameters (dict or [{key,value}, ...]) to a flat map."""
    out: dict[str, str] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            k = str(key or "").strip()
            v = str(value or "").strip()
            if k and v:
                out[k] = v[:150]
        return out
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            k = str(item.get("key") or item.get("name") or "").strip()
            v = str(item.get("value") or "").strip()
            if k and v:
                out[k] = v[:150]
    return out


def fetch_form_tracking_parameters(form_id: str) -> dict[str, str]:
    """Instant Form tracking_parameters (e.g. utm_content=dm) configured in Meta."""
    if not form_id:
        return {}
    try:
        data = _graph_get(str(form_id), {"fields": "tracking_parameters"})
        return _normalize_tracking_param_map(data.get("tracking_parameters"))
    except Exception:
        logger.exception("Failed to fetch Meta form tracking_parameters form_id=%s", form_id)
        return {}


def fetch_ad_details(ad_id: str) -> dict[str, str]:
    """Ad name + url_tags from Ads Manager (for Instant Form → CRM UTM mapping)."""
    if not ad_id:
        return {"name": "", "url_tags": ""}
    try:
        data = _graph_get(str(ad_id), {"fields": "url_tags,name"})
        return {
            "name": str(data.get("name") or "").strip(),
            "url_tags": str(data.get("url_tags") or "").strip(),
        }
    except Exception:
        logger.exception("Failed to fetch Meta ad details ad_id=%s", ad_id)
        return {"name": "", "url_tags": ""}


def fetch_ad_url_tags(ad_id: str) -> str:
    """
    Ad-level URL parameters from Ads Manager (url_tags).

    Agency example often lives here:
      utm_source=facebook_lead_ads&utm_medium=...&utm_campaign=...&utm_content=dm
    """
    details = fetch_ad_details(ad_id)
    if details.get("url_tags"):
        return details["url_tags"]
    # Some setups put the query string in the ad name; keep raw name as fallback parse source.
    return details.get("name") or ""


def parse_utm_query_string(raw: str) -> dict[str, str]:
    """Parse utm_* (and gclid) from a query string or full URL."""
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        from urllib.parse import parse_qs, urlparse, unquote

        candidate = text
        if "://" in text or text.startswith("?"):
            parsed = urlparse(text if "://" in text else f"https://x.local/{text}")
            candidate = parsed.query or text.lstrip("?")
        elif "utm_" not in text.lower() and "=" not in text:
            return {}

        # Allow bare "utm_source=facebook_lead_ads&utm_content=dm"
        if "utm_" in candidate.lower() or "gclid=" in candidate.lower():
            qs = parse_qs(candidate, keep_blank_values=False)
        else:
            # Maybe the whole string is embedded; extract query-looking segment.
            match = re.search(r"(utm_[^=&\s]+=[^&\s]+(?:&[^=&\s]+=[^&\s]+)*)", text, flags=re.I)
            if not match:
                return {}
            qs = parse_qs(match.group(1), keep_blank_values=False)

        out: dict[str, str] = {}
        for key in ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "gclid"):
            values = qs.get(key) or qs.get(key.upper()) or []
            if values and str(values[0]).strip():
                out[key] = unquote(str(values[0]).strip())[:150]
        return out
    except Exception:
        logger.exception("Failed to parse UTM query string")
        return {}


def form_name_to_utm_token(form_name: str) -> str:
    """
    Instant Form display name → UTM medium/campaign token.

    Example naming only:
      BCWW TK Andhra Pradesh All Interest P1
      → BCWW_TK_Andhra_Pradesh_All_Interest_P1
    """
    text = str(form_name or "").strip()
    if not text:
        return ""
    text = re.sub(r"[\s\-]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def _pick_passed_utm(*sources: dict[str, Any], keys: tuple[str, ...]) -> str:
    """Return the first non-empty UTM value literally passed by Meta/agency."""
    for src in sources:
        if not isinstance(src, dict):
            continue
        for key in keys:
            value = src.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text[:150]
    return ""


def meta_instant_form_utm_fields(
    *,
    form_name: str = "",
    form_id: str = "",
    ad_id: str = "",
    ad_name: str = "",
    adset_name: str = "",
    campaign_name: str = "",
    lead_payload: dict[str, Any] | None = None,
    webhook_value: dict[str, Any] | None = None,
    fields: dict[str, Any] | None = None,
    form_tracking: dict[str, str] | None = None,
    ad_url_tags: str = "",
) -> dict[str, str]:
    """
    Map Instant Form data onto CRM UTM columns.

    Instant Forms do not send utm_* names. This mapping applies to every
    Instant Form (all states / segments / R1 / R2), not one geography.

      utm_source   ← facebook_lead_ads (or a real utm_source if present)
      utm_medium   ← form_name
      utm_campaign ← campaign_name, else form_name
      utm_content  ← utm_content if present, else ad_id
      utm_term     ← utm_term if present, else adset_name

    CRM still labels the column utm_content. Instant Form value is ad_id.
    """
    payload = lead_payload or {}
    webhook = webhook_value or {}
    mapped = fields or {}
    tracking = form_tracking or {}
    from_ad_tags = parse_utm_query_string(ad_url_tags)
    form_token = form_name_to_utm_token(form_name)
    campaign_token = form_name_to_utm_token(campaign_name) or str(campaign_name or "").strip()
    adset_token = str(adset_name or "").strip() or form_name_to_utm_token(adset_name)
    ad_id_token = strip_meta_export_prefix(ad_id)

    source = (
        _pick_passed_utm(payload, webhook, mapped, tracking, from_ad_tags, keys=("utm_source", "utmSource"))
        or "facebook_lead_ads"
    )
    medium = (
        _pick_passed_utm(payload, webhook, mapped, tracking, from_ad_tags, keys=("utm_medium", "utmMedium"))
        or form_token
        or "meta_instant_form"
    )
    campaign = (
        _pick_passed_utm(
            payload,
            webhook,
            mapped,
            tracking,
            from_ad_tags,
            keys=("utm_campaign", "utmCampaign", "campaign"),
        )
        or campaign_token
        or form_token
        or form_id
        or ad_id_token
        or medium
    )
    content = (
        _pick_passed_utm(payload, webhook, mapped, tracking, from_ad_tags, keys=("utm_content", "utmContent"))
        or ad_id_token
    )
    term = (
        _pick_passed_utm(payload, webhook, mapped, tracking, from_ad_tags, keys=("utm_term", "utmTerm"))
        or adset_token
    )

    return {
        "utm_source": source[:150],
        "utm_medium": medium[:150],
        "utm_campaign": campaign[:150],
        "utm_content": content[:150],
        "utm_term": term[:150],
    }


def _field_map(field_data: list[dict[str, Any]] | None) -> dict[str, str]:
    mapped: dict[str, str] = {}
    extras: list[str] = []
    for item in field_data or []:
        name = str(item.get("name") or "").strip()
        values = item.get("values") or []
        value = str(values[0]).strip() if values else ""
        if not name:
            continue
        key = _FIELD_ALIASES.get(name.lower())
        if key:
            mapped[key] = value
        else:
            # Capture UTM fields if agency/Meta passes them on the Instant Form.
            utm_key = {
                "utm_source": "utm_source",
                "utmsource": "utm_source",
                "utm_medium": "utm_medium",
                "utmmedium": "utm_medium",
                "utm_campaign": "utm_campaign",
                "utmcampaign": "utm_campaign",
                "utm_content": "utm_content",
                "utmcontent": "utm_content",
                "utm_term": "utm_term",
                "utmterm": "utm_term",
            }.get(name.lower().replace(" ", "").strip())
            if utm_key and value:
                mapped[utm_key] = value
                continue
            track_key = _TRACKING_FIELD_ALIASES.get(_normalize_meta_field_key(name))
            if track_key:
                if value and not _is_unresolved_meta_macro(value):
                    mapped[track_key] = value
                continue
            extras.append(f"{name}: {value}")
            # Soft-match custom franchise questions
            lower = name.lower().replace("_", " ")
            if "investment" in lower and value:
                mapped.setdefault("investment_answer", value)
            if "space" in lower or "sq" in lower:
                mapped.setdefault("space_answer", value)
            if "when do you want" in lower or "start a preschool" in lower or (
                "start" in lower and "preschool" in lower
            ):
                mapped.setdefault("start_answer", value)
            if ("city" in lower or "location" in lower or "centre" in lower or "center" in lower) and value:
                mapped.setdefault("city", value)
            if "state" in lower and value:
                mapped.setdefault("state", value)
            if ("post" in lower and "code" in lower) or "pincode" in lower or "pin code" in lower:
                mapped.setdefault("post_code", value)
    if extras:
        mapped["extra_qa"] = "\n".join(extras)
    return mapped


def _infer_location_from_form_name(form_name: str) -> tuple[str, str]:
    """Return (city, state) guessed from Instant Form name."""
    text = (form_name or "").lower()
    city_state = [
        ("hyderabad", "Hyderabad", "Telangana"),
        ("secunderabad", "Secunderabad", "Telangana"),
        ("telangana", "", "Telangana"),
        ("bangalore", "Bengaluru", "Karnataka"),
        ("bengaluru", "Bengaluru", "Karnataka"),
        ("karnataka", "", "Karnataka"),
        ("chennai", "Chennai", "Tamil Nadu"),
        ("coimbatore", "Coimbatore", "Tamil Nadu"),
        ("tamil nadu", "", "Tamil Nadu"),
        ("madurai", "Madurai", "Tamil Nadu"),
        ("pune", "Pune", "Maharashtra"),
        ("mumbai", "Mumbai", "Maharashtra"),
        ("nagpur", "Nagpur", "Maharashtra"),
        ("maharashtra", "", "Maharashtra"),
        ("kolkata", "Kolkata", "West Bengal"),
        ("west bengal", "", "West Bengal"),
        ("kochi", "Kochi", "Kerala"),
        ("cochin", "Kochi", "Kerala"),
        ("trivandrum", "Thiruvananthapuram", "Kerala"),
        ("thiruvananthapuram", "Thiruvananthapuram", "Kerala"),
        ("kerala", "", "Kerala"),
        ("vijayawada", "Vijayawada", "Andhra Pradesh"),
        ("vizag", "Visakhapatnam", "Andhra Pradesh"),
        ("visakhapatnam", "Visakhapatnam", "Andhra Pradesh"),
        ("andhra pradesh", "", "Andhra Pradesh"),
        ("ahmedabad", "Ahmedabad", "Gujarat"),
        ("gujarat", "", "Gujarat"),
        ("jaipur", "Jaipur", "Rajasthan"),
        ("rajasthan", "", "Rajasthan"),
        ("delhi", "Delhi", "Delhi"),
        ("noida", "Noida", "Uttar Pradesh"),
        ("gurgaon", "Gurugram", "Haryana"),
        ("gurugram", "Gurugram", "Haryana"),
    ]
    for needle, city, state in city_state:
        if needle in text:
            return city, state
    return "", ""


def _infer_state_from_form_name(form_name: str) -> str:
    _city, state = _infer_location_from_form_name(form_name)
    return state


def already_imported(leadgen_id: str) -> bool:
    if not leadgen_id:
        return False
    if MetaLeadSuppress.objects.filter(leadgen_id=leadgen_id).exists():
        return True
    return CrmLead.objects.filter(raw_payload__meta_leadgen_id=leadgen_id).exists()


def suppress_meta_leadgen(
    leadgen_id: str,
    *,
    form_id: str = "",
    form_name: str = "",
    crm_lead_id: int | None = None,
) -> None:
    """
    Remember a Meta leadgen permanently.

    Used both when a lead is first imported and when a CRM row is deleted,
    so even a raw database DELETE cannot cause auto-sync to restore it.
    """
    leadgen_id = str(leadgen_id or "").strip()
    if not leadgen_id:
        return
    MetaLeadSuppress.objects.update_or_create(
        leadgen_id=leadgen_id,
        defaults={
            "form_id": str(form_id or "").strip()[:64],
            "form_name": str(form_name or "").strip()[:255],
            "crm_lead_id": crm_lead_id,
        },
    )


def suppress_meta_lead_from_crm_lead(lead: CrmLead) -> None:
    """If this CRM row came from Meta Instant Form, suppress its leadgen_id."""
    payload = lead.raw_payload if isinstance(lead.raw_payload, dict) else {}
    leadgen_id = str(payload.get("meta_leadgen_id") or "").strip()
    if not leadgen_id:
        return
    suppress_meta_leadgen(
        leadgen_id,
        form_id=str(payload.get("meta_form_id") or ""),
        form_name=str(payload.get("meta_form_name") or ""),
        crm_lead_id=getattr(lead, "pk", None),
    )


def mark_meta_leadgen_imported(
    *,
    leadgen_id: str,
    form_id: str = "",
    form_name: str = "",
    crm_lead_id: int | None = None,
) -> None:
    """Record Instant Form leadgen on first import so DB deletes won't re-sync it."""
    suppress_meta_leadgen(
        leadgen_id,
        form_id=form_id,
        form_name=form_name,
        crm_lead_id=crm_lead_id,
    )


def _claim_leadgen_import(leadgen_id: str) -> bool:
    """Cross-process short lock so webhook + multi-worker sync don't double-create."""
    if not leadgen_id:
        return False
    try:
        from django.core.cache import cache

        return bool(cache.add(f"meta_lead_import:{leadgen_id}", "1", timeout=900))
    except Exception:
        logger.exception("Meta lead import cache lock failed leadgen_id=%s", leadgen_id)
        return True


def create_crm_lead_from_meta(
    *,
    lead_payload: dict[str, Any],
    webhook_value: dict[str, Any],
    form_name: str = "",
) -> CrmLead:
    fields = _field_map(lead_payload.get("field_data"))
    raw_name = (fields.get("full_name") or "").strip()
    raw_phone = (fields.get("phone") or "").strip()
    raw_email = (fields.get("email") or "").strip().lower()
    raw_city = (fields.get("city") or "").strip()
    is_test_lead = any(
        _is_meta_test_value(v)
        for v in (raw_name, raw_phone, raw_city, fields.get("investment_answer", ""), fields.get("space_answer", ""))
    ) or raw_email in {"test@meta.com", "test@fb.com"}

    full_name = _clean_text(raw_name, fallback="Meta Test Lead" if is_test_lead else "Meta Lead")
    mobile = normalize_indian_mobile(raw_phone)
    if not mobile and is_test_lead:
        # Meta Lead Ads Testing Tool sends placeholder phone text, not digits.
        mobile = "9999999999"
    email = "" if _is_meta_test_value(raw_email) else raw_email
    if is_test_lead and not email:
        email = "test@meta.com"
    city = _clean_text(raw_city, fallback="Test City" if is_test_lead else "")
    city_label = city
    # Only verified R1 forms have controlled city dropdowns. Older forms remain
    # free-text and must retain the old state-only routing rule.
    if city and not is_test_lead and form_name in BCWW_TK_KERALA_R1_FORM_NAMES:
        crm_city, display_city = normalize_meta_city(city)
        city = crm_city or display_city or city
        city_label = display_city or city
    state = (fields.get("state") or "").strip()
    inferred_city, inferred_state = _infer_location_from_form_name(form_name)
    if not state:
        state = inferred_state
    if not city:
        city = inferred_city
        city_label = city
    post_code = (fields.get("post_code") or "").strip()
    if post_code and _is_meta_test_value(post_code):
        post_code = ""

    comments_parts = []
    if fields.get("extra_qa"):
        comments_parts.append(fields["extra_qa"])
    comments_parts.append("Source: Meta Lead Ads (Instant Form)")
    if form_name:
        comments_parts.append(f"Form: {form_name}")
    if post_code:
        comments_parts.append(f"Pincode: {post_code}")
    if is_test_lead:
        comments_parts.append("Meta Lead Ads Testing Tool lead (dummy field values).")

    investment_range = ""
    investment_answer = (fields.get("investment_answer") or "").strip()
    if investment_answer.lower() in ("yes", "y") or (
        is_test_lead and investment_answer and not _is_meta_test_value(investment_answer)
    ):
        investment_range = "₹10–15L"
    elif is_test_lead:
        investment_range = "₹10–15L"

    expected_start = _clean_text(fields.get("start_answer") or "", fallback="Test" if is_test_lead else "")
    if expected_start and expected_start != "Test":
        expected_start = _format_meta_choice_label(expected_start)

    leadgen_id = _first_tracking_id(
        lead_payload.get("id"),
        webhook_value.get("leadgen_id"),
        fields.get("id"),
    )
    form_id = _first_tracking_id(
        lead_payload.get("form_id"),
        webhook_value.get("form_id"),
        fields.get("form_id"),
    )
    form_tracking = fetch_form_tracking_parameters(form_id) if form_id else {}
    # Same columns as Ads Manager Instant Form CSV:
    # id, created_time, ad_id, ad_name, adset_id, adset_name, campaign_id,
    # campaign_name, form_id, form_name, is_organic, platform
    ad_id = _first_tracking_id(
        lead_payload.get("ad_id"),
        webhook_value.get("ad_id"),
        webhook_value.get("adgroup_id"),
        fields.get("ad_id"),
        form_tracking.get("ad_id"),
    )
    adset_id = _first_tracking_id(
        lead_payload.get("adset_id"),
        webhook_value.get("adset_id"),
        fields.get("adset_id"),
        form_tracking.get("adset_id"),
    )
    campaign_id = _first_tracking_id(
        lead_payload.get("campaign_id"),
        webhook_value.get("campaign_id"),
        fields.get("campaign_id"),
        form_tracking.get("campaign_id"),
    )
    ad_name = _first_tracking_text(
        lead_payload.get("ad_name"),
        webhook_value.get("ad_name"),
        fields.get("ad_name"),
        form_tracking.get("ad_name"),
    )
    adset_name = _first_tracking_text(
        lead_payload.get("adset_name"),
        webhook_value.get("adset_name"),
        fields.get("adset_name"),
        form_tracking.get("adset_name"),
    )
    campaign_name = _first_tracking_text(
        lead_payload.get("campaign_name"),
        webhook_value.get("campaign_name"),
        fields.get("campaign_name"),
        form_tracking.get("campaign_name"),
    )
    if not form_name:
        form_name = _first_tracking_text(
            lead_payload.get("form_name"),
            webhook_value.get("form_name"),
            fields.get("form_name"),
            form_tracking.get("form_name"),
        )
    platform = _first_tracking_text(
        lead_payload.get("platform"),
        webhook_value.get("platform"),
        fields.get("platform"),
        form_tracking.get("platform"),
    )
    is_organic_raw = _first_tracking_text(
        lead_payload.get("is_organic"),
        webhook_value.get("is_organic"),
        fields.get("is_organic"),
        form_tracking.get("is_organic"),
    )
    fbclid = _first_tracking_id(fields.get("fbclid"), form_tracking.get("fbclid"))
    ad_details = fetch_ad_details(ad_id) if ad_id else {"name": "", "url_tags": ""}
    if not ad_name:
        ad_name = ad_details.get("name") or ""
    ad_url_tags = ad_details.get("url_tags") or ""
    if not ad_url_tags and ad_name:
        ad_url_tags = ad_name
    utm = meta_instant_form_utm_fields(
        form_name=form_name,
        form_id=form_id,
        ad_id=ad_id,
        ad_name=ad_name,
        adset_name=adset_name,
        campaign_name=campaign_name,
        lead_payload=lead_payload,
        webhook_value=webhook_value,
        fields=fields,
        form_tracking=form_tracking,
        ad_url_tags=ad_url_tags,
    )

    raw_payload = {
        "meta_leadgen_id": leadgen_id,
        "meta_form_id": form_id,
        "meta_form_name": form_name,
        "meta_ad_id": ad_id,
        "meta_ad_name": ad_name,
        "meta_adset_id": adset_id,
        "meta_adset_name": adset_name,
        "meta_campaign_id": campaign_id,
        "meta_campaign_name": campaign_name,
        "meta_ad_url_tags": ad_url_tags,
        "meta_form_tracking_parameters": form_tracking,
        "meta_platform": platform,
        "meta_is_organic": is_organic_raw,
        "meta_fbclid": fbclid,
        "meta_page_id": str(webhook_value.get("page_id") or ""),
        "meta_created_time": lead_payload.get("created_time") or webhook_value.get("created_time"),
        "meta_field_data": lead_payload.get("field_data") or [],
        "meta_webhook_value": webhook_value,
        "meta_is_test_lead": is_test_lead,
        "meta_post_code": post_code,
        "meta_city_raw": raw_city,
        "meta_city_label": city_label,
        "pageType": "facebook_lead_ads",
        "campaign": utm["utm_campaign"] or form_name or form_id,
        "source": "july_meta",
        "utm_source": utm["utm_source"],
        "utm_medium": utm["utm_medium"],
        "utm_campaign": utm["utm_campaign"],
        "utm_content": utm["utm_content"],
    }

    if not mobile:
        raise ValueError("Meta lead is missing a phone number.")

    if leadgen_id and already_imported(leadgen_id):
        existing = CrmLead.objects.filter(raw_payload__meta_leadgen_id=leadgen_id).order_by("-id").first()
        if existing:
            return existing

    lead = CrmLead.objects.create(
        full_name=full_name,
        mobile=mobile,
        email=email,
        state=state,
        city=city,
        preferred_centre_location=city_label or city,
        investment_range=investment_range,
        expected_start_date=expected_start,
        comments="\n".join(comments_parts).strip(),
        source=CrmLeadSource.JULY_META,
        landing_page_url="",
        utm_source=utm["utm_source"],
        utm_medium=utm["utm_medium"],
        utm_campaign=utm["utm_campaign"],
        utm_content=utm["utm_content"],
        utm_term=utm["utm_term"],
        raw_payload=raw_payload,
    )
    # Permanent ledger: deleting this CRM row (even via SQL) must not re-import.
    if leadgen_id:
        mark_meta_leadgen_imported(
            leadgen_id=leadgen_id,
            form_id=form_id,
            form_name=form_name,
            crm_lead_id=lead.pk,
        )
    return lead


def process_leadgen_event(
    webhook_value: dict[str, Any],
    *,
    form_name: str | None = None,
) -> dict[str, Any]:
    leadgen_id = _first_tracking_id(webhook_value.get("leadgen_id"))
    if not leadgen_id:
        return {"ok": False, "error": "missing_leadgen_id"}

    early_form_id = _first_tracking_id(webhook_value.get("form_id"))
    early_form_name = (form_name or "").strip()
    if early_form_name or early_form_id:
        if early_form_name and not is_allowed_meta_form(
            form_id=early_form_id, form_name=early_form_name
        ):
            return {
                "ok": True,
                "skipped": True,
                "leadgen_id": leadgen_id,
                "reason": "form_not_allowed",
                "form_name": early_form_name,
                "form_id": early_form_id,
            }

    if is_before_sync_cutoff(webhook_value.get("created_time")):
        return {
            "ok": True,
            "skipped": True,
            "leadgen_id": leadgen_id,
            "reason": "before_sync_since",
        }

    if already_imported(leadgen_id):
        return {"ok": True, "skipped": True, "leadgen_id": leadgen_id}

    if not _claim_leadgen_import(leadgen_id):
        return {"ok": True, "skipped": True, "leadgen_id": leadgen_id, "reason": "import_in_progress"}

    # Re-check after claiming lock (another worker may have finished).
    if already_imported(leadgen_id):
        return {"ok": True, "skipped": True, "leadgen_id": leadgen_id}

    lead_payload = fetch_lead_by_id(leadgen_id)
    if is_before_sync_cutoff(lead_payload.get("created_time") or webhook_value.get("created_time")):
        return {
            "ok": True,
            "skipped": True,
            "leadgen_id": leadgen_id,
            "reason": "before_sync_since",
        }

    form_id = _first_tracking_id(lead_payload.get("form_id"), webhook_value.get("form_id"))
    resolved_form_name = (form_name or "").strip()
    if not resolved_form_name and form_id:
        resolved_form_name = fetch_form_name(form_id)

    if not is_allowed_meta_form(form_id=form_id, form_name=resolved_form_name):
        return {
            "ok": True,
            "skipped": True,
            "leadgen_id": leadgen_id,
            "reason": "form_not_allowed",
            "form_name": resolved_form_name,
            "form_id": form_id,
        }

    lead = create_crm_lead_from_meta(
        lead_payload=lead_payload,
        webhook_value=webhook_value,
        form_name=resolved_form_name,
    )

    try:
        from .emails import (
            lead_source_label_for_crm_lead,
            assign_and_notify_new_lead,
            send_crm_lead_enquiry_emails,
        )

        try:
            send_crm_lead_enquiry_emails(lead)
        except Exception:
            logger.exception(
                "CRM parent/team emails failed for Meta lead id=%s crm_id=%s",
                leadgen_id,
                lead.pk,
            )
        try:
            assign_and_notify_new_lead(
                lead,
                lead_source=lead_source_label_for_crm_lead(lead),
            )
        except Exception:
            logger.exception(
                "CRM auto-assign/notify failed for Meta lead id=%s crm_id=%s",
                leadgen_id,
                lead.pk,
            )
    except Exception:
        logger.exception("CRM post-create hooks failed for Meta lead id=%s crm_id=%s", leadgen_id, lead.pk)

    return {"ok": True, "crm_lead_id": lead.pk, "leadgen_id": leadgen_id}


def sync_page_leads(*, per_form_limit: int = 20, max_forms: int = 200) -> dict[str, Any]:
    """
    Poll Meta Instant Forms for new leads and import into CRM.

    Use as a reliable auto-sync backup while webhook delivery is Pending
    (common for unpublished / new apps). Dedupes via meta_leadgen_id.

    Honours META_LEADS_SYNC_SINCE and the BCWW TK name prefix so only
    paid-campaign Instant Forms are imported — not old city forms.
    """
    page_id = meta_page_id()
    since = meta_leads_sync_since()
    prefixes = meta_leads_form_prefixes()
    forms: list[dict[str, Any]] = []
    after: str | None = None
    form_cap = max(1, min(max_forms, 500))
    while len(forms) < form_cap:
        params: dict[str, str] = {
            "fields": "id,name",
            "limit": str(min(100, form_cap - len(forms))),
        }
        if after:
            params["after"] = after
        forms_payload = _graph_get(f"{page_id}/leadgen_forms", params)
        batch = forms_payload.get("data") or []
        forms.extend(batch)
        after = ((forms_payload.get("paging") or {}).get("cursors") or {}).get("after")
        if not after or not batch:
            break
    forms = forms[:form_cap]
    summary = {
        "ok": True,
        "page_id": page_id,
        "forms_total": len(forms),
        "forms": 0,
        "imported": 0,
        "skipped": 0,
        "skipped_old": 0,
        "skipped_form": 0,
        "failed": 0,
        "sync_since": since.isoformat() if since else None,
        "form_prefixes": prefixes,
        "results": [],
    }

    lead_query: dict[str, str] = {
        "fields": (
            "id,created_time,form_id,ad_id,ad_name,adset_id,adset_name,"
            "campaign_id,campaign_name,field_data,platform,is_organic"
        ),
        "limit": str(max(1, min(per_form_limit, 50))),
    }
    if since is not None:
        # Meta Lead Ads filtering — only leads created after cutoff.
        lead_query["filtering"] = json.dumps(
            [
                {
                    "field": "time_created",
                    "operator": "GREATER_THAN",
                    "value": int(since.timestamp()),
                }
            ]
        )

    for form in forms:
        form_id = str(form.get("id") or "").strip()
        form_name = str(form.get("name") or "").strip()
        if not form_id:
            continue
        if not is_allowed_meta_form(form_id=form_id, form_name=form_name):
            summary["skipped_form"] += 1
            continue
        summary["forms"] += 1
        try:
            leads_payload = _graph_get(f"{form_id}/leads", lead_query)
        except Exception as exc:
            # Some forms reject filtering — fall back and rely on local cutoff.
            if "filtering" in lead_query:
                try:
                    fallback = {
                        "fields": lead_query["fields"],
                        "limit": lead_query["limit"],
                    }
                    leads_payload = _graph_get(f"{form_id}/leads", fallback)
                except Exception as exc2:
                    logger.exception("Meta form leads fetch failed form_id=%s", form_id)
                    summary["failed"] += 1
                    summary["results"].append(
                        {"ok": False, "form_id": form_id, "error": str(exc2)}
                    )
                    continue
            else:
                logger.exception("Meta form leads fetch failed form_id=%s", form_id)
                summary["failed"] += 1
                summary["results"].append({"ok": False, "form_id": form_id, "error": str(exc)})
                continue

        for lead in leads_payload.get("data") or []:
            leadgen_id = _first_tracking_id(lead.get("id"))
            if not leadgen_id:
                continue
            if is_before_sync_cutoff(lead.get("created_time")):
                summary["skipped_old"] += 1
                summary["skipped"] += 1
                continue
            if already_imported(leadgen_id):
                summary["skipped"] += 1
                continue
            try:
                result = process_leadgen_event(
                    {
                        "leadgen_id": leadgen_id,
                        "form_id": str(lead.get("form_id") or form_id),
                        "page_id": page_id,
                        "created_time": lead.get("created_time"),
                        "ad_id": lead.get("ad_id") or "",
                        "ad_name": lead.get("ad_name") or "",
                        "adset_id": lead.get("adset_id") or "",
                        "adset_name": lead.get("adset_name") or "",
                        "campaign_id": lead.get("campaign_id") or "",
                        "campaign_name": lead.get("campaign_name") or "",
                    },
                    form_name=form_name,
                )
                summary["results"].append(result)
                if result.get("reason") == "before_sync_since":
                    summary["skipped_old"] += 1
                    summary["skipped"] += 1
                elif result.get("reason") == "form_not_allowed":
                    summary["skipped_form"] += 1
                    summary["skipped"] += 1
                elif result.get("skipped"):
                    summary["skipped"] += 1
                elif result.get("ok"):
                    summary["imported"] += 1
                else:
                    summary["failed"] += 1
            except Exception as exc:
                logger.exception("Meta lead sync failed leadgen_id=%s", leadgen_id)
                summary["failed"] += 1
                summary["results"].append(
                    {"ok": False, "leadgen_id": leadgen_id, "form_id": form_id, "error": str(exc)}
                )

    return summary
