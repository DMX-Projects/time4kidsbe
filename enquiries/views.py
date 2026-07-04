from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import LenientJWTAuthentication
from accounts.permissions import IsAdminUser, IsFranchiseUser
from .permissions import can_view_crm_leads, can_view_landing_leads
from accounts.profile_access import franchise_profile_for_user

from .landing_submit import handle_landing_enquiry_post
from .models import CrmLead, Enquiry, FranchiseEnquiry, KidsEnquiry, OTPVerification
from .serializers import (
    CrmLeadSerializer,
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


def _admin_enquiry_scope(qs, admin_user):
    """HO super admins see every enquiry; other admins are scoped to franchises they own."""
    if getattr(admin_user, "is_superuser", False):
        return qs
    return qs.filter(Q(franchise__isnull=True) | Q(franchise__admin=admin_user))


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
            _admin_enquiry_scope(Enquiry.objects.all(), admin_user)
            .select_related("franchise")
            .order_by("-created_at")
        )
        f_qs = (
            _admin_enquiry_scope(FranchiseEnquiry.objects.all(), admin_user)
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
            _admin_enquiry_scope(Enquiry.objects.all(), admin_user)
            .select_related("franchise")
            .order_by("-created_at")
        )
        f_qs = (
            _admin_enquiry_scope(FranchiseEnquiry.objects.all(), admin_user)
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
        return _admin_enquiry_scope(
            Enquiry.objects.all(), admin_user
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
        return _admin_enquiry_scope(
            FranchiseEnquiry.objects.all(), admin_user
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


@method_decorator(csrf_exempt, name="dispatch")
class CrmLeadCreateView(generics.CreateAPIView):
    """Public CRM form submit for /crm/web, /crm/fb, and /crm/insta."""

    serializer_class = CrmLeadSerializer
    permission_classes = [permissions.AllowAny]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class AdminCrmLeadListView(APIView):
    """Paginated CRM leads list — clone-compatible `{ leads, total }` response."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not can_view_crm_leads(request):
            return Response(
                {"detail": "CRM login required. Sign in with a CRM account to view CRM leads."},
                status=status.HTTP_403_FORBIDDEN,
            )

        from .crm_api import unified_leads_page, unified_leads_total

        try:
            page = max(1, int(request.query_params.get("page") or 1))
        except ValueError:
            page = 1
        try:
            limit = min(100, max(1, int(request.query_params.get("limit") or 10)))
        except ValueError:
            limit = 10

        total = unified_leads_total(request)
        leads = unified_leads_page(request, page=page, limit=limit)
        return Response({"leads": leads, "total": total})


class AdminCrmLeadDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        if not can_view_crm_leads(request):
            return Response({"detail": "CRM login required."}, status=status.HTTP_403_FORBIDDEN)
        from .crm_api import lead_to_dict, parse_lead_id, unified_lead_detail

        kind, _ = parse_lead_id(pk)
        if kind == "crm":
            lead = CrmLead.objects.filter(pk=parse_lead_id(pk)[1]).prefetch_related("notes").first()
            if not lead:
                return Response({"message": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)
            return Response(lead_to_dict(lead, include_detail=True))

        data = unified_lead_detail(pk, include_detail=True)
        if not data:
            return Response({"message": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(data)

    def patch(self, request, pk):
        if not can_view_crm_leads(request):
            return Response({"detail": "CRM login required."}, status=status.HTTP_403_FORBIDDEN)

        from .crm_api import update_unified_lead

        try:
            data = update_unified_lead(pk, request.data or {}, include_detail=True)
        except ValueError as exc:
            return Response({"message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not data:
            return Response({"message": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(data)


class AdminCrmLeadStatsView(APIView):
    """CRM dashboard stats — clone-compatible response."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not can_view_crm_leads(request):
            return Response(
                {"detail": "CRM login required. Sign in with a CRM account to view CRM leads."},
                status=status.HTTP_403_FORBIDDEN,
            )

        from .crm_api import unified_dashboard_stats

        return Response(unified_dashboard_stats(request))


class AdminCrmLeadRemindersView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not can_view_crm_leads(request):
            return Response({"detail": "CRM login required."}, status=status.HTTP_403_FORBIDDEN)

        from .crm_api import unified_reminders

        return Response(unified_reminders(request))


class AdminCrmLeadNoteCreateView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        if not can_view_crm_leads(request):
            return Response({"detail": "CRM login required."}, status=status.HTTP_403_FORBIDDEN)

        from .crm_api import note_to_dict, parse_lead_id

        kind, numeric_id = parse_lead_id(pk)
        if kind != "crm":
            return Response(
                {"message": "Notes can only be added to CRM campaign leads."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lead = CrmLead.objects.filter(pk=numeric_id).first()
        if not lead:
            return Response({"message": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)

        content = (request.data.get("content") or "").strip()
        if not content:
            return Response({"message": "Note content is required."}, status=status.HTTP_400_BAD_REQUEST)

        from .models import CrmLeadNote

        note = CrmLeadNote.objects.create(lead=lead, content=content)
        return Response(note_to_dict(note), status=status.HTTP_201_CREATED)


class AdminCrmSendReminderView(APIView):
    """Stub — clone UI expects success; actual email/WhatsApp handled client-side."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not can_view_crm_leads(request):
            return Response({"detail": "CRM login required."}, status=status.HTTP_403_FORBIDDEN)
        return Response({"success": True})


class AdminCrmCentresView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not can_view_crm_leads(request):
            return Response({"detail": "CRM login required."}, status=status.HTTP_403_FORBIDDEN)

        from franchises.franchise_geo import filter_queryset_by_city
        from franchises.models import Franchise

        qs = Franchise.objects.filter(is_active=True).order_by("name")
        city = (request.query_params.get("city") or "").strip()
        if city:
            qs = filter_queryset_by_city(qs, city)

        centres = [{"id": str(f.id), "name": f.name} for f in qs]
        return Response(centres)


class AdminCrmCitiesView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not can_view_crm_leads(request):
            return Response({"detail": "CRM login required."}, status=status.HTTP_403_FORBIDDEN)

        from .crm_api import unified_crm_cities

        cities = unified_crm_cities()
        return Response([{"name": city} for city in cities])


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
