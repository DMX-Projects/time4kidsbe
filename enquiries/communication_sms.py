"""Send OTP SMS to the mobile number the user entered on the form."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

OTP_API_URL = os.getenv(
    "SMS_OTP_API_URL",
    "https://communication.t4e.in/api/external-sms/send-otp",
).strip()

# Approved T.I.M.E. KIDS DLT template — {#var#} = 4-digit OTP.
OTP_MESSAGE_TEMPLATE = (
    "One time password (OTP) for verifying your mobile number is {#var#} - T.I.M.E. KIDS"
)


def normalize_mobile(raw: str) -> str:
    """Return 10-digit Indian mobile, or empty string if invalid."""
    phone_digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if len(phone_digits) == 12 and phone_digits.startswith("91"):
        phone_digits = phone_digits[2:]
    elif len(phone_digits) == 11 and phone_digits.startswith("0"):
        phone_digits = phone_digits[1:]
    if len(phone_digits) == 10 and phone_digits[0] in "6789":
        return phone_digits
    return ""


def build_otp_message(code: str) -> str:
    return OTP_MESSAGE_TEMPLATE.replace("{#var#}", str(code))


def send_otp_sms(phone: str, code: str) -> tuple[bool, str, dict]:
    """
    Send OTP to the given mobile (the number typed in the form).

    curl --location 'https://communication.t4e.in/api/external-sms/send-otp' \\
      --header 'X-API-Key: <SMS_API_KEY>' \\
      --header 'Content-Type: application/json' \\
      --data '{
        "mobile": "XXXXXXXXXX",
        "message": "One time password (OTP) for verifying your mobile number is XXXX - T.I.M.E. KIDS"
      }'
    """
    api_key = (
        os.getenv("SMS_API_KEY", "").strip()
        or os.getenv("COMMUNICATION_API_KEY", "").strip()
    )
    if not api_key:
        return False, "SMS API key is not configured.", {}

    api_url = OTP_API_URL

    phone_digits = normalize_mobile(phone)
    if not phone_digits:
        return False, "Invalid mobile number.", {}

    otp_code = str(code).strip()
    if not otp_code.isdigit() or len(otp_code) != 4:
        return False, "OTP must be a 4-digit code.", {}

    # Gateway expects 10-digit mobile (no 91 prefix) — same as working Postman/curl.
    payload = {
        "mobile": phone_digits,
        "message": build_otp_message(otp_code),
    }
    body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        api_url,
        data=body,
        headers={
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8", "replace")
            status_code = getattr(response, "status", 200)
            try:
                data = json.loads(raw) if raw else {}
            except ValueError:
                data = {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        status_code = exc.code
        try:
            data = json.loads(raw) if raw else {}
        except ValueError:
            data = {}
    except Exception as exc:
        logger.exception("OTP SMS request failed for %s", phone_digits)
        return False, str(exc), {}

    meta = {"mobile": phone_digits, "message_id": None}

    if status_code in (200, 201) and data.get("success") is True:
        results = data.get("results") or []
        if results and isinstance(results, list):
            meta["message_id"] = results[0].get("messageId")
            # Prefer the mobile the gateway echoed back.
            echoed = results[0].get("mobile")
            if echoed:
                meta["mobile"] = str(echoed)
        logger.info(
            "OTP SMS sent to entered mobile=%s gateway_mobile=%s messageId=%s message=%r",
            phone_digits,
            meta["mobile"],
            meta["message_id"],
            payload["message"],
        )
        return True, data.get("message") or "OTP sent successfully.", meta

    detail = (
        data.get("message")
        or data.get("detail")
        or data.get("error")
        or raw
        or f"SMS API returned status {status_code}"
    )
    logger.warning(
        "OTP SMS failed for entered mobile=%s: status=%s detail=%s",
        phone_digits,
        status_code,
        detail,
    )
    return False, str(detail), meta
