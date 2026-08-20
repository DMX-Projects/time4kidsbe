"""Meta Conversions API — CRM / Conversion Leads events.

Sends Instant Form lead stage changes from TIME Kids CRM back to the dataset
so Events Manager can optimize for qualified leads.

Payload: https://developers.facebook.com/docs/marketing-api/conversions-api/conversion-leads-integration/payload-specification/
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)

DEFAULT_DATASET_ID = "1502626011898766"
DEFAULT_API_VERSION = "v26.0"
LEAD_EVENT_SOURCE = "TIME Kids CRM"
ACTION_SOURCE = "system_generated"
EVENT_SOURCE = "crm"

# Untouched / first CRM row = Meta's initial raw-lead stage.
_INITIAL_STATUSES = frozenset({"", "untouched", "new"})

# These CRM stages are sent after a counsellor updates the lead.
# Untouched is not a qualified stage, but a new Instant Form still sends "Lead"
# so Meta lead coverage can reach ~60%.
# Not answering, not interested, and wrong enquiry are never sent.
QUALIFIED_CRM_STATUSES = frozenset(
    {
        "follow_up",
        "join_later",
        "cold",
        "warm",
        "hot",
        "converted_mou_signed",
        "converted_agreement_signed",
    }
)


def meta_capi_dataset_id() -> str:
    return (
        getattr(settings, "META_CAPI_DATASET_ID", "")
        or os.getenv("META_CAPI_DATASET_ID")
        or DEFAULT_DATASET_ID
    ).strip() or DEFAULT_DATASET_ID


def meta_capi_api_version() -> str:
    raw = (
        getattr(settings, "META_CAPI_API_VERSION", "")
        or os.getenv("META_CAPI_API_VERSION")
        or DEFAULT_API_VERSION
    ).strip()
    if raw and not raw.startswith("v"):
        raw = f"v{raw}"
    return raw or DEFAULT_API_VERSION


def meta_capi_access_token() -> str:
    return (
        getattr(settings, "META_CAPI_ACCESS_TOKEN", "")
        or os.getenv("META_CAPI_ACCESS_TOKEN")
        or ""
    ).strip()


def meta_capi_lead_event_source() -> str:
    return (
        getattr(settings, "META_CAPI_LEAD_EVENT_SOURCE", "")
        or os.getenv("META_CAPI_LEAD_EVENT_SOURCE")
        or LEAD_EVENT_SOURCE
    ).strip() or LEAD_EVENT_SOURCE


def meta_capi_test_event_code() -> str:
    return (
        getattr(settings, "META_CAPI_TEST_EVENT_CODE", "")
        or os.getenv("META_CAPI_TEST_EVENT_CODE")
        or ""
    ).strip()


def meta_capi_is_configured() -> bool:
    return bool(meta_capi_access_token() and meta_capi_dataset_id())


def hash_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_email(raw: str) -> str:
    return str(raw or "").strip().lower()


def normalize_phone_e164_digits(raw: str, *, country_code: str = "91") -> str:
    """Digits-only phone with country code (India default). Do not hash yet."""
    digits = re.sub(r"\D", "", str(raw or ""))
    if not digits:
        return ""
    cc = re.sub(r"\D", "", country_code) or "91"
    if digits.startswith(cc) and len(digits) >= 10 + len(cc):
        return digits
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"{cc}{digits}"
    return digits


def _strip_for_name(raw: str) -> str:
    text = str(raw or "").strip().lower()
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _strip_for_place(raw: str) -> str:
    text = str(raw or "").strip().lower()
    return re.sub(r"[^a-z0-9]", "", text)


def split_name(full_name: str) -> tuple[str, str]:
    parts = [p for p in _strip_for_name(full_name).split(" ") if p]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[-1]


def is_qualified_capi_status(status: str) -> bool:
    """True only for team-defined qualified franchise CRM stages."""
    return str(status or "").strip().lower() in QUALIFIED_CRM_STATUSES


def should_upload_capi_event(status: str, *, event_name: str | None = None) -> bool:
    """Allow qualified stages, plus the initial Lead event for new Instant Forms."""
    if is_qualified_capi_status(status):
        return True
    name = (event_name or "").strip()
    status_key = str(status or "").strip().lower()
    return name == "Lead" and status_key in _INITIAL_STATUSES


def event_name_for_status(status: str) -> str:
    """Free-form CRM stage name. Initial raw lead is always 'Lead'."""
    value = str(status or "").strip()
    if value.lower() in _INITIAL_STATUSES:
        return "Lead"
    from .models import CrmLeadStatus

    for choice in CrmLeadStatus:
        if choice.value == value:
            return str(choice.label)
    return value or "Lead"


def meta_leadgen_id_from_lead(lead: Any) -> str:
    payload = getattr(lead, "raw_payload", None)
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("meta_leadgen_id") or "").strip()


def _parse_lead_id(raw: str) -> int | None:
    digits = re.sub(r"\D", "", str(raw or ""))
    if 15 <= len(digits) <= 17:
        try:
            return int(digits)
        except ValueError:
            return None
    return None


def _fbclid_from_lead(lead: Any) -> str:
    payload = getattr(lead, "raw_payload", None)
    if not isinstance(payload, dict):
        payload = {}
    for key in ("fbclid", "meta_fbclid", "fbc"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    url = str(getattr(lead, "landing_page_url", "") or "").strip()
    if not url or "fbclid=" not in url.lower():
        return ""
    try:
        return str((parse_qs(urlparse(url).query).get("fbclid") or [""])[0] or "").strip()
    except Exception:
        return ""


def _fbc_value(fbclid: str, event_time: int) -> str:
    raw = str(fbclid or "").strip()
    if not raw:
        return ""
    if raw.startswith("fb."):
        return raw
    return f"fb.1.{int(event_time)}.{raw}"


def _unix_ts(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        ts = int(value)
        if ts > 10_000_000_000:
            ts //= 1000
        return ts if ts > 0 else None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return _unix_ts(int(text))
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp())
    except ValueError:
        return None


def _lead_generated_time(lead: Any) -> int | None:
    payload = getattr(lead, "raw_payload", None)
    if isinstance(payload, dict):
        ts = _unix_ts(payload.get("meta_created_time"))
        if ts:
            return ts
    return _unix_ts(getattr(lead, "created_at", None))


def build_user_data(lead: Any, *, event_time: int) -> dict[str, Any]:
    user_data: dict[str, Any] = {}
    lead_id = _parse_lead_id(meta_leadgen_id_from_lead(lead))
    if lead_id is not None:
        user_data["lead_id"] = lead_id

    fbc = _fbc_value(_fbclid_from_lead(lead), event_time)
    if fbc:
        user_data["fbc"] = fbc

    email = normalize_email(getattr(lead, "email", "") or "")
    if email and "@" in email:
        user_data["em"] = [hash_sha256(email)]

    phone = normalize_phone_e164_digits(getattr(lead, "mobile", "") or "")
    if phone:
        user_data["ph"] = [hash_sha256(phone)]

    first, last = split_name(getattr(lead, "full_name", "") or "")
    if first:
        user_data["fn"] = [hash_sha256(first)]
    if last:
        user_data["ln"] = [hash_sha256(last)]

    city = _strip_for_place(getattr(lead, "city", "") or "")
    if city:
        user_data["ct"] = [hash_sha256(city)]

    state = _strip_for_place(getattr(lead, "state", "") or "")
    if state:
        user_data["st"] = [hash_sha256(state)]

    user_data["country"] = [hash_sha256("in")]

    payload = getattr(lead, "raw_payload", None)
    if isinstance(payload, dict):
        pin = re.sub(r"\D", "", str(payload.get("meta_post_code") or ""))
        if len(pin) >= 5:
            user_data["zp"] = [hash_sha256(pin)]

    return user_data


def build_crm_event(
    lead: Any,
    *,
    event_name: str | None = None,
    event_time: int | None = None,
) -> dict[str, Any] | None:
    """Return one Conversions API event, or None if matching data is too thin."""
    name = (event_name or event_name_for_status(getattr(lead, "status", "") or "")).strip() or "Lead"
    now = int(time.time())
    generated = _lead_generated_time(lead) or 0
    ts = int(event_time) if event_time else now
    # Meta discards CRM events timestamped before the Instant Form lead was created.
    if generated and ts < generated:
        ts = generated + 1
    if ts > now:
        ts = now

    user_data = build_user_data(lead, event_time=ts)
    if not user_data:
        return None
    if "lead_id" not in user_data and "em" not in user_data and "ph" not in user_data and "fbc" not in user_data:
        return None

    event_id = f"tkcrm:{meta_leadgen_id_from_lead(lead) or getattr(lead, 'pk', '')}:{name}:{ts}"
    return {
        "event_name": name,
        "event_time": ts,
        "event_id": event_id[:100],
        "action_source": ACTION_SOURCE,
        "user_data": user_data,
        "custom_data": {
            "event_source": EVENT_SOURCE,
            "lead_event_source": meta_capi_lead_event_source(),
        },
    }


def build_payload(
    events: list[dict[str, Any]],
    *,
    test_event_code: str = "",
) -> dict[str, Any]:
    body: dict[str, Any] = {"data": events}
    code = (test_event_code or "").strip()
    if code:
        body["test_event_code"] = code
    return body


def _events_url() -> str:
    return f"https://graph.facebook.com/{meta_capi_api_version()}/{meta_capi_dataset_id()}/events"


def post_crm_events(
    events: list[dict[str, Any]],
    *,
    test_event_code: str = "",
    timeout: int = 15,
) -> dict[str, Any]:
    if not events:
        return {"ok": False, "skipped": True, "reason": "empty_events"}
    token = meta_capi_access_token()
    if not token:
        return {"ok": False, "skipped": True, "reason": "not_configured"}

    body = build_payload(events, test_event_code=test_event_code)
    body["access_token"] = token
    encoded = json.dumps(body).encode("utf-8")
    req = Request(
        _events_url(),
        data=encoded,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
            return {"ok": True, "response": data}
    except HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = ""
        logger.warning("Meta CAPI HTTP %s: %s", exc.code, err_body or exc.reason)
        return {"ok": False, "error": f"HTTP {exc.code}", "detail": err_body or str(exc.reason)}
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        logger.warning("Meta CAPI request failed: %s", exc)
        return {"ok": False, "error": str(exc)}


def send_crm_stage_event(
    lead: Any,
    *,
    event_name: str | None = None,
    event_time: int | None = None,
    test_event_code: str = "",
) -> dict[str, Any]:
    """Build and POST one CRM stage event for a campaign lead."""
    if not meta_capi_is_configured():
        return {"ok": False, "skipped": True, "reason": "not_configured"}
    if not meta_leadgen_id_from_lead(lead):
        return {"ok": False, "skipped": True, "reason": "not_meta_instant_form"}
    status = getattr(lead, "status", "") or ""
    name = (event_name or event_name_for_status(status)).strip() or "Lead"
    if not should_upload_capi_event(status, event_name=name):
        return {"ok": False, "skipped": True, "reason": "not_qualified_status"}

    event = build_crm_event(lead, event_name=name, event_time=event_time)
    if not event:
        return {"ok": False, "skipped": True, "reason": "insufficient_user_data"}

    code = (test_event_code or meta_capi_test_event_code()).strip()
    result = post_crm_events([event], test_event_code=code)
    if result.get("ok"):
        logger.info(
            "Meta CAPI sent event_name=%s crm_id=%s lead_id=%s events_received=%s",
            event.get("event_name"),
            getattr(lead, "pk", None),
            (event.get("user_data") or {}).get("lead_id"),
            (result.get("response") or {}).get("events_received"),
        )
    return {**result, "event_name": event.get("event_name"), "crm_lead_id": getattr(lead, "pk", None)}


def _send_async(lead_pk: int, event_name: str, event_time: int) -> None:
    try:
        from .models import CrmLead

        lead = CrmLead.objects.filter(pk=lead_pk).first()
        if not lead:
            return
        send_crm_stage_event(lead, event_name=event_name, event_time=event_time)
    except Exception:
        logger.exception("Meta CAPI background send failed crm_id=%s event_name=%s", lead_pk, event_name)


def _run_in_thread(lead_pk: int, event_name: str, event_time: int) -> None:
    thread = threading.Thread(
        target=_send_async,
        args=(lead_pk, event_name, event_time),
        daemon=True,
        name=f"meta-capi-{lead_pk}",
    )
    thread.start()


def schedule_crm_stage_event(lead: Any, *, event_name: str | None = None) -> None:
    """Fire a CAPI upload after the CRM row commits. Never raises to the request."""
    try:
        if not meta_capi_is_configured():
            return
        if not meta_leadgen_id_from_lead(lead):
            return
        status = getattr(lead, "status", "") or ""
        name = (event_name or event_name_for_status(status)).strip() or "Lead"
        if not should_upload_capi_event(status, event_name=name):
            return
        pk = getattr(lead, "pk", None)
        if not pk:
            return
        event_time = int(time.time())

        def _after_commit() -> None:
            _run_in_thread(int(pk), name, event_time)

        try:
            transaction.on_commit(_after_commit)
        except Exception:
            _after_commit()
    except Exception:
        logger.exception(
            "Meta CAPI schedule failed crm_id=%s",
            getattr(lead, "pk", None),
        )
