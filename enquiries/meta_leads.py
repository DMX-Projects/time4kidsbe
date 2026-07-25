"""Meta Lead Ads → TIME Kids CRM helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

from .models import CrmLead, CrmLeadSource

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

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


def meta_page_access_token() -> str:
    return (getattr(settings, "META_PAGE_ACCESS_TOKEN", "") or "").strip()


def meta_webhook_verify_token() -> str:
    return (getattr(settings, "META_WEBHOOK_VERIFY_TOKEN", "") or "").strip()


def meta_app_secret() -> str:
    return (getattr(settings, "META_APP_SECRET", "") or "").strip()


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


def _graph_get(path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    token = meta_page_access_token()
    if not token:
        raise RuntimeError("META_PAGE_ACCESS_TOKEN is not configured.")

    query = dict(params or {})
    query["access_token"] = token
    url = f"{GRAPH_BASE}/{path.lstrip('/')}?{urlencode(query)}"
    req = Request(url, method="GET", headers={"Accept": "application/json"})
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_lead_by_id(leadgen_id: str) -> dict[str, Any]:
    return _graph_get(str(leadgen_id), {"fields": "id,created_time,ad_id,adset_id,campaign_id,form_id,field_data"})


def fetch_form_name(form_id: str) -> str:
    if not form_id:
        return ""
    try:
        data = _graph_get(str(form_id), {"fields": "name"})
        return str(data.get("name") or "").strip()
    except Exception:
        logger.exception("Failed to fetch Meta form name for form_id=%s", form_id)
        return ""


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
            extras.append(f"{name}: {value}")
            # Soft-match custom franchise questions
            lower = name.lower()
            if "investment" in lower and value:
                mapped.setdefault("investment_answer", value)
            if "space" in lower or "sq" in lower:
                mapped.setdefault("space_answer", value)
            if "when do you want" in lower or "start a preschool" in lower or "start" in lower:
                mapped.setdefault("start_answer", value)
    if extras:
        mapped["extra_qa"] = "\n".join(extras)
    return mapped


def _infer_state_from_form_name(form_name: str) -> str:
    text = (form_name or "").lower()
    states = [
        ("tamil nadu", "Tamil Nadu"),
        ("karnataka", "Karnataka"),
        ("andhra pradesh", "Andhra Pradesh"),
        ("kerala", "Kerala"),
        ("telangana", "Telangana"),
        ("maharashtra", "Maharashtra"),
        ("west bengal", "West Bengal"),
        ("gujarat", "Gujarat"),
        ("delhi", "Delhi"),
        ("rajasthan", "Rajasthan"),
        ("madhya pradesh", "Madhya Pradesh"),
    ]
    for needle, label in states:
        if needle in text:
            return label
    return ""


def already_imported(leadgen_id: str) -> bool:
    if not leadgen_id:
        return False
    return CrmLead.objects.filter(raw_payload__meta_leadgen_id=leadgen_id).exists()


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
    state = (fields.get("state") or "").strip() or _infer_state_from_form_name(form_name)

    comments_parts = []
    if fields.get("extra_qa"):
        comments_parts.append(fields["extra_qa"])
    comments_parts.append("Source: Meta Lead Ads (Instant Form)")
    if form_name:
        comments_parts.append(f"Form: {form_name}")
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

    leadgen_id = str(
        lead_payload.get("id")
        or webhook_value.get("leadgen_id")
        or ""
    ).strip()
    form_id = str(lead_payload.get("form_id") or webhook_value.get("form_id") or "").strip()
    ad_id = str(lead_payload.get("ad_id") or webhook_value.get("ad_id") or "").strip()

    raw_payload = {
        "meta_leadgen_id": leadgen_id,
        "meta_form_id": form_id,
        "meta_form_name": form_name,
        "meta_ad_id": ad_id,
        "meta_page_id": str(webhook_value.get("page_id") or ""),
        "meta_created_time": lead_payload.get("created_time") or webhook_value.get("created_time"),
        "meta_field_data": lead_payload.get("field_data") or [],
        "meta_webhook_value": webhook_value,
        "meta_is_test_lead": is_test_lead,
        "pageType": "facebook_lead_ads",
        "campaign": form_name or form_id,
        "source": "july_meta",
    }

    if not mobile:
        raise ValueError("Meta lead is missing a phone number.")

    lead = CrmLead.objects.create(
        full_name=full_name,
        mobile=mobile,
        email=email,
        state=state,
        city=city,
        preferred_centre_location=city,
        investment_range=investment_range,
        expected_start_date=expected_start,
        comments="\n".join(comments_parts).strip(),
        source=CrmLeadSource.JULY_META,
        landing_page_url="",
        utm_source="facebook_lead_ads",
        utm_medium=form_name or "meta_instant_form",
        utm_campaign=form_name or form_id or ad_id,
        raw_payload=raw_payload,
    )
    return lead


def process_leadgen_event(webhook_value: dict[str, Any]) -> dict[str, Any]:
    leadgen_id = str(webhook_value.get("leadgen_id") or "").strip()
    if not leadgen_id:
        return {"ok": False, "error": "missing_leadgen_id"}

    if already_imported(leadgen_id):
        return {"ok": True, "skipped": True, "leadgen_id": leadgen_id}

    lead_payload = fetch_lead_by_id(leadgen_id)
    form_id = str(lead_payload.get("form_id") or webhook_value.get("form_id") or "").strip()
    form_name = fetch_form_name(form_id) if form_id else ""

    lead = create_crm_lead_from_meta(
        lead_payload=lead_payload,
        webhook_value=webhook_value,
        form_name=form_name,
    )

    try:
        from .emails import (
            lead_source_label_for_crm_lead,
            send_crm_heads_new_lead_reminder,
            send_crm_lead_enquiry_emails,
        )

        send_crm_lead_enquiry_emails(lead)
        send_crm_heads_new_lead_reminder(
            name=lead.full_name or "",
            lead_source=lead_source_label_for_crm_lead(lead),
            centre_name=lead.preferred_centre_location or lead.city or "",
        )
    except Exception:
        logger.exception("CRM emails failed for Meta lead id=%s crm_id=%s", leadgen_id, lead.pk)

    return {"ok": True, "crm_lead_id": lead.pk, "leadgen_id": leadgen_id}
