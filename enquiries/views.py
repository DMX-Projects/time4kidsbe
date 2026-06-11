from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import LenientJWTAuthentication
from accounts.permissions import IsAdminUser, IsFranchiseUser
from .permissions import can_view_landing_leads
from accounts.profile_access import franchise_profile_for_user

from .landing_submit import handle_landing_enquiry_post
from .models import Enquiry, FranchiseEnquiry, KidsEnquiry, OTPVerification
from .serializers import (
    EnquirySerializer,
    FranchiseEnquiryCreateSerializer,
    FranchiseEnquiryReadSerializer,
    FranchiseEnquiryStatusSerializer,
    KidsEnquirySerializer,
)


def _slugify_city(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace(" ", "-")
        .replace("_", "-")
    )


def _resolve_kids_enquiry_city(city_param: str) -> str | None:
    """Map URL slug (e.g. ``new-delhi``) to a stored ``kids_enquiry.city`` value."""
    raw = (city_param or "").strip()
    if not raw or raw.lower() == "all":
        return None

    label = raw.replace("-", " ").replace("_", " ").strip()
    if KidsEnquiry.objects.filter(city__iexact=label).exists():
        return label

    slug = _slugify_city(raw)
    for stored in (
        KidsEnquiry.objects.exclude(city__isnull=True)
        .exclude(city="")
        .values_list("city", flat=True)
        .distinct()
    ):
        if _slugify_city(stored) == slug:
            return stored
    return label


def _distinct_kids_enquiry_cities() -> list[str]:
    cities = (
        KidsEnquiry.objects.exclude(city__isnull=True)
        .exclude(city="")
        .values_list("city", flat=True)
        .distinct()
    )
    return sorted({c.strip() for c in cities if c and c.strip()}, key=str.casefold)


def _sync_enquiry_status_siblings(instance, status: str) -> None:
    """One public submit can create several rows (global + per-centre). Keep status in sync."""
    phone = (getattr(instance, "phone", None) or "").strip()
    if not phone:
        return
    type(instance).objects.filter(phone=phone).exclude(pk=instance.pk).update(status=status)


class EnquiryStatusSyncMixin:
    def perform_update(self, serializer):
        instance = serializer.save()
        _sync_enquiry_status_siblings(instance, instance.status)


def _merge_enquiry_rows(
    enquiry_qs,
    franchise_qs,
    enquiry_type_filter: str | None,
):
    rows: list[tuple] = []
    for obj in enquiry_qs:
        rows.append((obj.created_at, EnquirySerializer(obj).data))
    for obj in franchise_qs:
        rows.append((obj.created_at, FranchiseEnquiryReadSerializer(obj).data))
    rows.sort(key=lambda x: x[0], reverse=True)
    payload = [r[1] for r in rows]
    if enquiry_type_filter == "FRANCHISE":
        return [p for p in payload if p.get("enquiry_type") == "FRANCHISE"]
    if enquiry_type_filter in ("ADMISSION", "CONTACT"):
        return [p for p in payload if p.get("enquiry_type") == enquiry_type_filter]
    return payload


@method_decorator(csrf_exempt, name="dispatch")
class LandingEnquirySubmitView(View):
    """HTML form POST from legacy landing pages → ``kids_enquiry`` + redirect."""

    def post(self, request, *args, **kwargs):
        return handle_landing_enquiry_post(request.POST)


@method_decorator(csrf_exempt, name="dispatch")
class EnquiryCreateView(generics.CreateAPIView):
    serializer_class = EnquirySerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        enquiry: Enquiry = serializer.save()
        self._send_notifications(enquiry)

    def _send_notifications(self, enquiry: Enquiry) -> None:
        import logging
        import traceback

        logger = logging.getLogger(__name__)

        try:
            from .emails import send_enquiry_email

            email_sent = send_enquiry_email(enquiry)

            if email_sent:
                logger.info(f"Email notification sent for enquiry from {enquiry.name}")
            else:
                logger.warning(f"Failed to send email notification for enquiry from {enquiry.name}")
        except Exception as e:
            logger.error(f"Error sending enquiry email notification: {str(e)}")
            logger.error(traceback.format_exc())


@method_decorator(csrf_exempt, name="dispatch")
class FranchiseEnquiryCreateView(generics.CreateAPIView):
    serializer_class = FranchiseEnquiryCreateSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        lead: FranchiseEnquiry = serializer.save()
        self._send_notifications(lead)

    def _send_notifications(self, lead: FranchiseEnquiry) -> None:
        import logging
        import traceback

        logger = logging.getLogger(__name__)

        try:
            from .emails import send_franchise_enquiry_email

            email_sent = send_franchise_enquiry_email(lead)

            if email_sent:
                logger.info(f"Email notification sent for franchise lead from {lead.name}")
            else:
                logger.warning(f"Failed to send email notification for franchise lead from {lead.name}")
        except Exception as e:
            logger.error(f"Error sending franchise enquiry email notification: {str(e)}")
            logger.error(traceback.format_exc())


class AdminEnquiryListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, *args, **kwargs):
        admin_user = request.user
        e_qs = (
            Enquiry.objects.filter(Q(franchise__isnull=True) | Q(franchise__admin=admin_user))
            .select_related("franchise")
            .order_by("-created_at")
        )
        f_qs = (
            FranchiseEnquiry.objects.filter(Q(franchise__isnull=True) | Q(franchise__admin=admin_user))
            .select_related("franchise")
            .order_by("-created_at")
        )
        data = _merge_enquiry_rows(e_qs, f_qs, None)
        return Response(data)


class FranchiseEnquiryListView(APIView):
    permission_classes = [IsFranchiseUser]

    def get(self, request, *args, **kwargs):
        franchise = franchise_profile_for_user(request.user)
        if not franchise:
            return Response([])
        e_qs = Enquiry.objects.filter(franchise=franchise).select_related("franchise").order_by("-created_at")
        f_qs = FranchiseEnquiry.objects.filter(franchise=franchise).select_related("franchise").order_by(
            "-created_at"
        )
        data = _merge_enquiry_rows(e_qs, f_qs, None)
        return Response(data)


class AdminAllEnquiryListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, *args, **kwargs):
        admin_user = request.user
        e_qs = (
            Enquiry.objects.filter(Q(franchise__isnull=True) | Q(franchise__admin=admin_user))
            .select_related("franchise")
            .order_by("-created_at")
        )
        f_qs = (
            FranchiseEnquiry.objects.filter(Q(franchise__isnull=True) | Q(franchise__admin=admin_user))
            .select_related("franchise")
            .order_by("-created_at")
        )
        enquiry_type = request.query_params.get("type")
        data = _merge_enquiry_rows(e_qs, f_qs, enquiry_type)
        return Response(data)


class EnquiryUpdateView(EnquiryStatusSyncMixin, generics.UpdateAPIView):
    serializer_class = EnquirySerializer
    permission_classes = [IsAdminUser]
    lookup_field = "pk"

    def get_queryset(self):
        admin_user = self.request.user
        return Enquiry.objects.filter(
            Q(franchise__isnull=True) | Q(franchise__admin=admin_user)
        ).select_related("franchise")


class FranchiseEnquiryUpdateView(EnquiryStatusSyncMixin, generics.UpdateAPIView):
    serializer_class = EnquirySerializer
    permission_classes = [IsFranchiseUser]
    lookup_field = "pk"

    def get_queryset(self):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return Enquiry.objects.none()
        return Enquiry.objects.filter(franchise=franchise)


class FranchiseLeadAdminUpdateView(EnquiryStatusSyncMixin, generics.UpdateAPIView):
    serializer_class = FranchiseEnquiryStatusSerializer
    permission_classes = [IsAdminUser]
    lookup_field = "pk"
    http_method_names = ["patch", "put", "head", "options"]

    def get_queryset(self):
        admin_user = self.request.user
        return FranchiseEnquiry.objects.filter(
            Q(franchise__isnull=True) | Q(franchise__admin=admin_user)
        ).select_related("franchise")


class FranchiseLeadPartnerUpdateView(EnquiryStatusSyncMixin, generics.UpdateAPIView):
    serializer_class = FranchiseEnquiryStatusSerializer
    permission_classes = [IsFranchiseUser]
    lookup_field = "pk"
    http_method_names = ["patch", "put", "head", "options"]

    def get_queryset(self):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return FranchiseEnquiry.objects.none()
        return FranchiseEnquiry.objects.filter(franchise=franchise).select_related("franchise")


class LandingKidsEnquiryListView(APIView):
    """Landing-page leads from ``kids_enquiry`` (admin report)."""

    authentication_classes = [LenientJWTAuthentication]
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        if not can_view_landing_leads(request):
            return Response(
                {
                    "detail": (
                        "Invalid or missing report key. "
                        "Use ?key=… or sign in as admin with Authorization: Bearer …"
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        city_param = request.query_params.get("city", "").strip()
        resolved_city = _resolve_kids_enquiry_city(city_param) if city_param else None

        qs = KidsEnquiry.objects.all().order_by("-created_date")
        if resolved_city:
            qs = qs.filter(city__iexact=resolved_city)

        data = KidsEnquirySerializer(qs, many=True).data
        return Response(
            {
                "count": len(data),
                "city": resolved_city,
                "cities": _distinct_kids_enquiry_cities(),
                "results": data,
            }
        )


import os
import random
from django.http import JsonResponse

class SendOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        phone = request.data.get("phone", "").strip()
        if not phone:
            return JsonResponse({"detail": "Phone number is required."}, status=400)

        # Generate 6-digit OTP
        code = str(random.randint(100000, 999999))

        # Save to database
        OTPVerification.objects.update_or_create(
            phone=phone,
            defaults={"code": code}
        )

        # Get Twilio credentials from settings
        account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
        auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
        twilio_phone = os.getenv("TWILIO_PHONE_NUMBER", "").strip()

        # Format phone number for Twilio (prefix with +91 if needed and doesn't start with +)
        twilio_to_phone = phone
        if not twilio_to_phone.startswith("+"):
            twilio_to_phone = f"+91{twilio_to_phone}"

        success = False
        error_msg = ""

        if account_sid and auth_token and twilio_phone:
            try:
                import requests
                from requests.auth import HTTPBasicAuth
                url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
                data = {
                    "To": twilio_to_phone,
                    "From": twilio_phone,
                    "Body": f"Your TimeKids verification code is: {code}"
                }
                response = requests.post(url, data=data, auth=HTTPBasicAuth(account_sid, auth_token), timeout=10)
                if response.status_code in [200, 201]:
                    success = True
                else:
                    error_msg = f"Twilio API returned status {response.status_code}: {response.text}"
            except Exception as e:
                error_msg = str(e)
        else:
            success = True
            error_msg = "TWILIO_NOT_CONFIGURED"

        return JsonResponse({
            "success": success,
            "detail": "OTP sent successfully." if success else "Failed to send OTP.",
            "error": error_msg,
            "code": code if not account_sid else None
        })


class VerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        phone = request.data.get("phone", "").strip()
        code = request.data.get("code", "").strip()
        if not phone or not code:
            return JsonResponse({"detail": "Phone and code are required."}, status=400)

        otp_record = OTPVerification.objects.filter(phone=phone).first()
        if otp_record and otp_record.code == code:
            return JsonResponse({"valid": True})
        return JsonResponse({"valid": False, "detail": "Invalid OTP code."}, status=400)
