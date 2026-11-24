"""Google Ads Lead Form webhook → TIME Kids CRM."""

from __future__ import annotations

import logging
import re
from typing import Any

from django.conf import settings
from django.core.cache import cache

from .meta_leads import normalize_indian_mobile
from .models import CrmLead, CrmLeadSource

logger = logging.getLogger(__name__)

# Google Ads Lead Form Key field allows at most 50 characters.
DEFAULT_GOOGLE_LEAD_WEBHOOK_KEY = "tk_google_leads_webhook_2026"

_COLUMN_ID_MAP = {
    "FULL_NAME": "full_name",
    "FIRST_NAME": "full_name",
    "LAST_NAME": "last_name",
    "EMAIL": "email",
    "PHONE_NUMBER": "phone",
    "WORK_PHONE": "phone",
    "CITY": "city",
    "REGION": "state",
    "STATE": "state",
    "POSTAL_CODE": "post_code",
    "ZIP_CODE": "post_code",
    "COMPANY_NAME": "company",
    "JOB_TITLE": "job_title",
}

_COLUMN_NAME_MAP = {
    "full name": "full_name",
    "name": "full_name",
    "email": "email",
    "user email": "email",
    "phone": "phone",
    "phone number": "phone",
    "user phone": "phone",
    "mobile": "phone",
    "city": "city",
    "state": "state",
    "region": "state",
    "postal code": "post_code",
    "zip code": "post_code",
}


def google_lead_webhook_key() -> str:
    configured = str(getattr(settings, "GOOGLE_LEAD_WEBHOOK_KEY", "") or "").strip()
    return configured or DEFAULT_GOOGLE_LEAD_WEBHOOK_KEY


def _first_nonempty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _payload_google_key(payload: dict[str, Any]) -> str:
    # Google samples use both google_key and Google_key.
    return _first_nonempty(payload.get("google_key"), payload.get("Google_key"))


def verify_google_lead_key(payload: dict[str, Any]) -> bool:
    expected = google_lead_webhook_key()
    if not expected:
        return False
    provided = _payload_google_key(payload)
    return bool(provided) and provided == expected


def _map_column(column_id: str, column_name: str) -> str:
    cid = str(column_id or "").strip().upper()
    if cid in _COLUMN_ID_MAP:
        return _COLUMN_ID_MAP[cid]
    name = re.sub(r"\s+", " ", str(column_name or "").strip().lower())
    if name in _COLUMN_NAME_MAP:
        return _COLUMN_NAME_MAP[name]
    if "phone" in name or "mobile" in name:
        return "phone"
    if "email" in name:
        return "email"
    if name in {"full name", "name"} or name.endswith(" name"):
        return "full_name"
    if "city" in name:
        return "city"
    if name in {"state", "region"} or "state" in name:
        return "state"
    return ""


def extract_user_columns(payload: dict[str, Any]) -> dict[str, str]:
    fields: dict[str, str] = {}
    extras: list[str] = []
    for row in payload.get("user_column_data") or []:
        if not isinstance(row, dict):
            continue
        value = str(row.get("string_value") or "").strip()
        if not value:
            continue
        key = _map_column(row.get("column_id") or "", row.get("column_name") or "")
        if not key:
            label = str(row.get("column_name") or row.get("column_id") or "Field").strip()
            extras.append(f"{label}: {value}")
            continue
        if key == "last_name":
            existing = fields.get("full_name") or ""
            fields["full_name"] = f"{existing} {value}".strip() if existing else value
            continue
        if key in fields and fields[key]:
            continue
        fields[key] = value
    if extras:
        fields["extra_qa"] = "\n".join(extras)
    return fields


def _resolve_state_from_city(city: str) -> str:
    city_name = (city or "").strip()
    if not city_name:
        return ""
    try:
        from franchises.franchise_geo import STATE_CODE_TO_NAME

        from .crm_users import resolve_lead_state_code

        code = resolve_lead_state_code(state="", city=city_name)
        if not code:
            return ""
        return STATE_CODE_TO_NAME.get(code, "") or code
    except Exception:
        logger.exception("Google lead city→state lookup failed for city=%s", city_name)
        return ""


def _already_imported(lead_id: str) -> bool:
    if not lead_id:
        return False
    return CrmLead.objects.filter(raw_payload__google_lead_id=lead_id).exists()


def _claim_import(lead_id: str) -> bool:
    if not lead_id:
        return True
    try:
        return bool(cache.add(f"google_lead_import:{lead_id}", "1", timeout=120))
    except Exception:
        logger.exception("Google lead import cache lock failed lead_id=%s", lead_id)
        return True


def create_crm_lead_from_google(payload: dict[str, Any]) -> CrmLead:
    fields = extract_user_columns(payload)
    is_test = bool(payload.get("is_test"))

    raw_name = (fields.get("full_name") or "").strip()
    raw_phone = (fields.get("phone") or "").strip()
    raw_email = (fields.get("email") or "").strip().lower()
    raw_city = (fields.get("city") or "").strip()
    raw_state = (fields.get("state") or "").strip()

    full_name = raw_name or ("Google Test Lead" if is_test else "Google Lead")
    mobile = normalize_indian_mobile(raw_phone)
    if not re.fullmatch(r"[6-9]\d{9}", mobile or ""):
        if is_test:
            mobile = "9999999999"
        else:
            mobile = mobile or ""
    email = raw_email
    if is_test and not email:
        email = "test@google-ads.example"
    city = raw_city or ("Test City" if is_test else "")
    state = raw_state or _resolve_state_from_city(city)

    lead_id = _first_nonempty(payload.get("lead_id"))
    form_id = _first_nonempty(payload.get("form_id"))
    campaign_id = _first_nonempty(payload.get("campaign_id"))
    adgroup_id = _first_nonempty(payload.get("adgroup_id"))
    creative_id = _first_nonempty(payload.get("creative_id"))
    gclid = _first_nonempty(payload.get("gcl_id"), payload.get("gclid"))
    asset_group_id = _first_nonempty(payload.get("asset_group_id"))
    api_version = _first_nonempty(payload.get("api_version"))
    lead_submit_time = _first_nonempty(payload.get("lead_submit_time"))
    lead_source = _first_nonempty(payload.get("lead_source")) or "LEAD_FORM"

    comments_parts = [
        "Source: Google Ads Lead Form",
    ]
    if form_id:
        comments_parts.append(f"Form ID: {form_id}")
    if campaign_id:
        comments_parts.append(f"Campaign ID: {campaign_id}")
    if fields.get("post_code"):
        comments_parts.append(f"Pincode: {fields['post_code']}")
    if fields.get("extra_qa"):
        comments_parts.append(fields["extra_qa"])
    if is_test:
        comments_parts.append("Google Ads Lead Form test lead.")

    raw_payload = {
        "google_lead_id": lead_id,
        "google_form_id": form_id,
        "google_campaign_id": campaign_id,
        "google_adgroup_id": adgroup_id,
        "google_creative_id": creative_id,
        "google_asset_group_id": asset_group_id,
        "google_gclid": gclid,
        "google_api_version": api_version,
        "google_is_test": is_test,
        "google_lead_submit_time": lead_submit_time,
        "google_lead_source": lead_source,
        "google_user_column_data": payload.get("user_column_data") or [],
        "google_webhook_payload": payload,
        "pageType": "google_lead_form",
        "campaign": str(campaign_id or form_id or "google_lead_form"),
        "source": "july_lp",
        "utm_source": "google",
        "utm_medium": "lead_form",
        "utm_campaign": str(campaign_id or ""),
        "gclid": gclid,
    }

    if not mobile:
        raise ValueError("Google lead is missing a phone number.")

    if lead_id and _already_imported(lead_id):
        existing = CrmLead.objects.filter(raw_payload__google_lead_id=lead_id).order_by("-id").first()
        if existing:
            return existing

    return CrmLead.objects.create(
        full_name=full_name[:255],
        mobile=mobile,
        email=email,
        state=state,
        city=city,
        preferred_centre_location=city,
        investment_range="₹10–15L",
        comments="\n".join(comments_parts).strip(),
        source=CrmLeadSource.JULY_LP,
        landing_page_url="",
        gclid=(gclid or "")[:255],
        utm_source="google",
        utm_medium="lead_form",
        utm_campaign=str(campaign_id or "")[:150],
        utm_content="",
        utm_term="",
        raw_payload=raw_payload,
    )


def process_google_lead_webhook(
    payload: dict[str, Any],
    *,
    send_emails: bool = True,
) -> dict[str, Any]:
    if not isinstance(payload, dict) or not payload:
        return {"ok": False, "error": "empty_payload"}

    if not verify_google_lead_key(payload):
        return {"ok": False, "error": "invalid_google_key"}

    lead_id = _first_nonempty(payload.get("lead_id"))
    if not lead_id:
        return {"ok": False, "error": "missing_lead_id"}

    if _already_imported(lead_id):
        return {"ok": True, "skipped": True, "lead_id": lead_id}

    if not _claim_import(lead_id):
        return {"ok": True, "skipped": True, "lead_id": lead_id, "reason": "import_in_progress"}

    if _already_imported(lead_id):
        return {"ok": True, "skipped": True, "lead_id": lead_id}

    lead = create_crm_lead_from_google(payload)

    try:
        from .emails import (
            assign_and_notify_new_lead,
            lead_source_label_for_crm_lead,
            send_crm_lead_enquiry_emails,
        )

        if send_emails and not bool(payload.get("is_test")):
            try:
                send_crm_lead_enquiry_emails(lead)
            except Exception:
                logger.exception(
                    "CRM parent/team emails failed for Google lead id=%s crm_id=%s",
                    lead_id,
                    lead.pk,
                )
        try:
            assign_and_notify_new_lead(
                lead,
                lead_source=lead_source_label_for_crm_lead(lead),
                notify=send_emails and not bool(payload.get("is_test")),
            )
        except Exception:
            logger.exception(
                "CRM auto-assign/notify failed for Google lead id=%s crm_id=%s",
                lead_id,
                lead.pk,
            )
    except Exception:
        logger.exception("CRM post-create hooks failed for Google lead id=%s", lead_id)

    return {"ok": True, "crm_lead_id": lead.pk, "lead_id": lead_id}
