import logging
import re
from dataclasses import dataclass
from typing import Any

from django.db import DatabaseError
from django.db.models import Q
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from franchises.franchise_geo import city_query_variants
from franchises.models import Franchise

from .models import Enquiry, EnquiryType, KidsEnquiry

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^\d{10}$")
LANDING_ENQUIRY_TYPE = "Admission Enquiry"


@dataclass
class LandingEnquiryRecord:
    """Normalized row for thank-you redirect and SendGrid templates."""

    pk: int
    name: str
    email: str
    mobileno: str
    city: str
    state: str
    location: str
    source: str
    centre_name: str
    centre_phone: str
    centre_email: str
    kids_enquiry_id: int | None = None

    @classmethod
    def from_kids_enquiry(cls, row: KidsEnquiry) -> "LandingEnquiryRecord":
        return cls(
            pk=row.pk,
            kids_enquiry_id=row.pk,
            name=row.name,
            email=row.email or "",
            mobileno=row.mobileno or "",
            city=row.city or "",
            state=row.state or "",
            location=row.location or "",
            source=row.source or "",
            centre_name=row.centre_name or "",
            centre_phone=row.centre_phone or "",
            centre_email=row.centre_email or "",
        )


def _post_value(data: Any, key: str) -> str:
    if hasattr(data, "get"):
        value = data.get(key, "")
    else:
        value = ""
    return str(value or "").strip()


def _lookup_franchise(city: str, location: str) -> Franchise | None:
    if not location:
        return None
    qs = Franchise.objects.filter(is_active=True, name__iexact=location)
    if city:
        city_q = Q()
        for variant in city_query_variants(city):
            city_q |= Q(city__iexact=variant)
        match = qs.filter(city_q).first()
        if match:
            return match
    return qs.first()


def _thank_you_path(source: str) -> str:
    if source.lower() == "facebook":
        return "/timekids-2g/thank-you-fb.html"
    return "/timekids-2g/thank-you.html"


def _centre_contact(franchise: Franchise | None) -> tuple[str, str, str]:
    if not franchise:
        return "", "", ""
    phone = (franchise.contact_phone or franchise.phoneno or "").strip()
    email = (franchise.contact_email or franchise.email or "").strip()
    return franchise.name, phone, email


def _raw_payload(post_data: Any) -> dict:
    if not hasattr(post_data, "keys"):
        return {}
    return {key: post_data.get(key) for key in post_data.keys()}


def _save_kids_enquiry_row(
    *,
    name: str,
    telephone: str,
    email: str,
    state: str,
    city: str,
    location: str,
    source: str,
    centre_name: str,
    centre_phone: str,
    centre_email: str,
    raw_payload: dict,
) -> KidsEnquiry:
    return KidsEnquiry.objects.create(
        name=name,
        mobile=telephone,
        mobileno=telephone,
        email=email,
        state=state,
        city=city,
        location=location,
        enquiry_type=LANDING_ENQUIRY_TYPE,
        source=source,
        centre_name=centre_name or location,
        centre_phone=centre_phone,
        centre_email=centre_email,
        raw_payload=raw_payload,
    )


def _save_enquiry_fallback(
    *,
    name: str,
    telephone: str,
    email: str,
    city: str,
    location: str,
    source: str,
    franchise: Franchise | None,
    centre_name: str,
    centre_phone: str,
    centre_email: str,
) -> LandingEnquiryRecord:
    """Persist to ``enquiry`` when ``kids_enquiry`` is missing or not migrated yet."""
    message_parts = [f"Location: {location}", f"Source: {source}"]
    if centre_phone:
        message_parts.append(f"Centre phone: {centre_phone}")
    if centre_email:
        message_parts.append(f"Centre email: {centre_email}")

    row = Enquiry.objects.create(
        enquiry_type=EnquiryType.ADMISSION,
        name=name,
        email=email,
        phone=telephone,
        message="\n".join(message_parts),
        franchise=franchise,
        city=city or (franchise.city if franchise else ""),
    )
    return LandingEnquiryRecord(
        pk=row.pk,
        kids_enquiry_id=None,
        name=name,
        email=email,
        mobileno=telephone,
        city=city or (franchise.city if franchise else ""),
        state=(franchise.state if franchise else "") or "",
        location=location,
        source=source,
        centre_name=centre_name or location,
        centre_phone=centre_phone,
        centre_email=centre_email,
    )


def save_landing_enquiry(post_data: Any) -> LandingEnquiryRecord:
    name = _post_value(post_data, "name")
    telephone = _post_value(post_data, "telephone")
    email = _post_value(post_data, "email")
    city = _post_value(post_data, "city")
    location = _post_value(post_data, "Location") or _post_value(post_data, "location")
    source = _post_value(post_data, "source") or "landing"

    if len(name) < 2:
        raise ValueError("Please enter a valid name.")
    if not PHONE_RE.match(telephone):
        raise ValueError("Please enter a valid 10-digit mobile number.")
    if not EMAIL_RE.match(email):
        raise ValueError("Please enter a valid email address.")
    if not location or location.lower() == "select location":
        raise ValueError("Please select a location.")

    franchise = _lookup_franchise(city, location)
    centre_name, centre_phone, centre_email = _centre_contact(franchise)
    state = (franchise.state if franchise else "") or ""
    raw_payload = _raw_payload(post_data)

    try:
        row = _save_kids_enquiry_row(
            name=name,
            telephone=telephone,
            email=email,
            state=state,
            city=city,
            location=location,
            source=source,
            centre_name=centre_name,
            centre_phone=centre_phone,
            centre_email=centre_email,
            raw_payload=raw_payload,
        )
        return LandingEnquiryRecord.from_kids_enquiry(row)
    except DatabaseError as exc:
        logger.warning(
            "kids_enquiry insert failed (%s); falling back to enquiry table. "
            "Run: python manage.py migrate enquiries",
            exc,
        )
        return _save_enquiry_fallback(
            name=name,
            telephone=telephone,
            email=email,
            city=city,
            location=location,
            source=source,
            franchise=franchise,
            centre_name=centre_name,
            centre_phone=centre_phone,
            centre_email=centre_email,
        )


def handle_landing_enquiry_post(post_data: Any):
    try:
        record = save_landing_enquiry(post_data)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    except Exception:
        logger.exception("Landing enquiry save failed")
        return HttpResponseBadRequest(
            "We could not save your enquiry. Please try again or contact the centre directly."
        )

    try:
        from .emails import send_landing_enquiry_emails

        email_status = send_landing_enquiry_emails(record)
        if email_status and record.kids_enquiry_id:
            KidsEnquiry.objects.filter(pk=record.kids_enquiry_id).update(email_status=email_status)
    except Exception:
        logger.exception("Landing enquiry email failed for id=%s", record.pk)

    source = _post_value(post_data, "source")
    return HttpResponseRedirect(_thank_you_path(source))
