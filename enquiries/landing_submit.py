import logging
import re
from typing import Any

from django.http import HttpResponseBadRequest, HttpResponseRedirect
from franchises.models import Franchise

from .models import KidsEnquiry

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^\d{10}$")
LANDING_ENQUIRY_TYPE = "Admission Enquiry"


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
        match = qs.filter(city__iexact=city).first()
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


def save_landing_enquiry(post_data: Any) -> KidsEnquiry:
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

    raw_payload = {key: post_data.get(key) for key in post_data.keys()} if hasattr(post_data, "keys") else {}

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


def handle_landing_enquiry_post(post_data: Any):
    try:
        record = save_landing_enquiry(post_data)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    try:
        from .emails import send_landing_enquiry_emails

        email_status = send_landing_enquiry_emails(record)
        if email_status:
            KidsEnquiry.objects.filter(pk=record.pk).update(email_status=email_status)
    except Exception:
        logger.exception("Landing enquiry email failed for id=%s", record.pk)

    source = _post_value(post_data, "source")
    return HttpResponseRedirect(_thank_you_path(source))
