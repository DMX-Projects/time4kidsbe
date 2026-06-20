import json

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from plp_api.services import enroll_plp_parent, upsert_plp_user, upsert_student_enrollment


@require_GET
def api_home(request):
    """Open in browser: https://your-django-site.com/api/plp/"""
    return JsonResponse(
        {
            "success": True,
            "service": "PLP Enrollment API",
            "description": (
                "TiKES / PLP pushes new parent enrollments here. "
                "Creates users + ParentProfile + StudentProfile for parent login."
            ),
            "endpoints": {
                "create_enrollment": {
                    "url": "/api/plp/create-enrollment/",
                    "method": "POST",
                    "note": "Recommended — one call creates user, parent profile, and student. (/api/plp/enroll/ also works.)",
                    "headers": {"Content-Type": "application/json", "X-API-Key": "required"},
                    "body": {
                        "username": "string (usually same as idcardno)",
                        "password": "string (plain)",
                        "code": "string (optional)",
                        "email": "string (or emailid)",
                        "full_name": "string (optional, or parentname)",
                        "state": "string",
                        "city": "string",
                        "centre": "string (must match a franchise name)",
                        "studentname": "string",
                        "class": "string",
                        "idcardno": "string",
                        "parentname": "string",
                        "emailid": "string",
                        "mobileno": "string",
                        "year": "string",
                        "batch_num": "integer (default 1)",
                    },
                },
                "create_user": {
                    "url": "/api/plp/create-user/",
                    "method": "POST",
                    "note": "User row only — call create-student-details after, or use create-enrollment/ instead.",
                    "headers": {"Content-Type": "application/json", "X-API-Key": "required"},
                    "body": {
                        "username": "string",
                        "password": "string (plain)",
                        "code": "string",
                        "email": "string",
                        "full_name": "string (optional)",
                    },
                },
                "create_student_details": {
                    "url": "/api/plp/create-student-details/",
                    "method": "POST",
                    "note": "Student + parent profile — user must exist or pass emailid/idcardno to match.",
                    "headers": {"Content-Type": "application/json", "X-API-Key": "required"},
                    "body": {
                        "username": "string (optional if idcardno set)",
                        "email": "string (optional if emailid set)",
                        "password": "string",
                        "state": "string",
                        "city": "string",
                        "centre": "string",
                        "studentname": "string",
                        "class": "string",
                        "idcardno": "string",
                        "parentname": "string",
                        "emailid": "string",
                        "mobileno": "string",
                        "year": "string",
                        "batch_num": "integer (default 1)",
                    },
                },
            },
        }
    )


def _api_key_valid(request):
    expected = getattr(settings, "PLP_API_KEY", "")
    if not expected:
        return False
    return request.headers.get("X-API-Key", "") == expected


def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _unauthorized():
    return JsonResponse({"success": False, "error": "Unauthorized"}, status=401)


def _bad_json():
    return JsonResponse({"success": False, "error": "Invalid JSON body"}, status=400)


def _missing_fields(fields):
    return JsonResponse(
        {"success": False, "error": "Missing fields: " + ", ".join(fields)},
        status=400,
    )


def _handle_enrollment_error(exc: Exception):
    message = str(exc)
    if "No franchise matched" in message:
        return JsonResponse({"success": False, "error": message}, status=404)
    if "already used" in message.lower():
        return JsonResponse({"success": False, "error": message}, status=409)
    return JsonResponse({"success": False, "error": message}, status=400)


@csrf_exempt
@require_POST
def create_enrollment(request):
    """Full enrollment: users + ParentProfile + StudentProfile (recommended for TiKES)."""
    if not _api_key_valid(request):
        return _unauthorized()

    data = _json_body(request)
    if not data:
        return _bad_json()

    required = ("password", "centre", "studentname", "class", "idcardno", "year")
    missing = [field for field in required if not str(data.get(field) or "").strip()]
    if not (data.get("username") or data.get("idcardno")):
        missing.append("username or idcardno")
    if not (data.get("email") or data.get("emailid")):
        missing.append("email or emailid")
    if missing:
        return _missing_fields(missing)

    try:
        result = enroll_plp_parent(data)
    except Exception as exc:
        return _handle_enrollment_error(exc)

    return JsonResponse(
        {
            "success": True,
            "message": "Enrollment complete",
            **result,
        }
    )


@csrf_exempt
@require_POST
def create_plp_user(request):
    if not _api_key_valid(request):
        return _unauthorized()

    data = _json_body(request)
    if not data:
        return _bad_json()

    required = ("username", "password", "code", "email")
    missing = [field for field in required if not str(data.get(field) or "").strip()]
    if missing:
        return _missing_fields(missing)

    try:
        user, created = upsert_plp_user(
            username=data["username"],
            password=data["password"],
            email=data["email"],
            code=data.get("code", ""),
            full_name=data.get("full_name") or data["username"],
        )
    except Exception as exc:
        return _handle_enrollment_error(exc)

    return JsonResponse(
        {
            "success": True,
            "message": "User created" if created else "User updated",
            "user_id": user.pk,
            "created": created,
            "username": user.username,
        }
    )


@csrf_exempt
@require_POST
def create_student_details(request):
    if not _api_key_valid(request):
        return _unauthorized()

    data = _json_body(request)
    if not data:
        return _bad_json()

    required = (
        "state",
        "city",
        "centre",
        "studentname",
        "class",
        "idcardno",
        "password",
        "parentname",
        "emailid",
        "mobileno",
        "year",
    )
    missing = [field for field in required if data.get(field) in (None, "")]
    if missing:
        return _missing_fields(missing)

    username = (data.get("username") or data.get("idcardno") or "").strip()
    email = (data.get("email") or data.get("emailid") or "").strip()
    if not username:
        return _missing_fields(["username or idcardno"])

    try:
        with transaction.atomic():
            user, user_created = upsert_plp_user(
                username=username,
                password=data["password"],
                email=email,
                code=data.get("code", ""),
                full_name=data.get("parentname") or username,
            )
            student, parent_profile, student_created, parent_created = upsert_student_enrollment(
                user,
                state=data["state"],
                city=data["city"],
                centre=data["centre"],
                studentname=data["studentname"],
                class_name=data["class"],
                idcardno=data["idcardno"],
                password=data["password"],
                batch_num=int(data.get("batch_num", 1) or 1),
                parentname=data["parentname"],
                emailid=data["emailid"],
                mobileno=data["mobileno"],
                year=data["year"],
            )
    except Exception as exc:
        return _handle_enrollment_error(exc)

    return JsonResponse(
        {
            "success": True,
            "message": "Student enrollment saved",
            "user_id": user.pk,
            "user_created": user_created,
            "parent_profile_id": parent_profile.pk,
            "parent_created": parent_created,
            "student_id": student.pk,
            "student_created": student_created,
            "franchise_id": parent_profile.franchise_id,
            "franchise_name": parent_profile.franchise.name if parent_profile.franchise_id else "",
            "username": user.username,
            "id_card_no": student.Idcardno,
        }
    )
