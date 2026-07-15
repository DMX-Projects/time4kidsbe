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
from .models import CrmLead, Enquiry, EnquiryType, FranchiseEnquiry, KidsEnquiry, OTPVerification
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
    updates = {"status": status}
    if hasattr(instance, "meeting_date"):
        updates["meeting_date"] = instance.meeting_date
    if hasattr(instance, "next_follow_up_date"):
        updates["next_follow_up_date"] = instance.next_follow_up_date
    type(instance).objects.filter(phone=phone).exclude(pk=instance.pk).update(**updates)


class EnquiryStatusSyncMixin:
    def perform_update(self, serializer):
        instance = serializer.save()
        _sync_enquiry_status_siblings(instance, instance.status)


def _admin_enquiry_scope(qs, admin_user):
    """HO super admins see every enquiry; other admins are scoped to franchises they own."""
    if getattr(admin_user, "is_superuser", False):
        if qs.model.__name__ == "FranchiseEnquiry":
            return qs.filter(franchise__isnull=True)
        return qs
    
    if qs.model.__name__ == "FranchiseEnquiry":
        return qs.filter(franchise__admin=admin_user)
        
    return qs.filter(Q(franchise__isnull=True) | Q(franchise__admin=admin_user))


def _ho_admin_enquiry_qs(qs):
    """HO/CRM meaningful leads only — exclude legacy imported rows (e.g. enquiry_type='general')."""
    return qs.filter(enquiry_type__in=[EnquiryType.ADMISSION, EnquiryType.CONTACT])


def _normalize_admin_type_filter(raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw.strip().upper()
    if value in ("ADMISSION", "CONTACT", "FRANCHISE"):
        return value
    return None


def _parse_admin_list_params(request) -> tuple[int, int]:
    try:
        page = max(1, int(request.query_params.get("page") or 1))
    except ValueError:
        page = 1
    try:
        limit = min(100, max(1, int(request.query_params.get("limit") or 20)))
    except ValueError:
        limit = 20
    return page, limit


def _apply_admin_enquiry_search(qs, search: str | None):
    term = (search or "").strip()
    if not term:
        return qs
    return qs.filter(
        Q(name__icontains=term)
        | Q(email__icontains=term)
        | Q(phone__icontains=term)
        | Q(city__icontains=term)
        | Q(message__icontains=term)
        | Q(franchise__name__icontains=term)
    )


def _admin_enquiry_tab_counts(admin_user) -> dict[str, int]:
    e_qs = _ho_admin_enquiry_qs(_admin_enquiry_scope(Enquiry.objects.all(), admin_user))
    f_qs = _admin_enquiry_scope(FranchiseEnquiry.objects.all(), admin_user)
    admission = e_qs.filter(enquiry_type=EnquiryType.ADMISSION).count()
    contact = e_qs.filter(enquiry_type=EnquiryType.CONTACT).count()
    franchise = f_qs.count()
    return {
        "all": admission + contact + franchise,
        "admission": admission,
        "contact": contact,
        "franchise": franchise,
    }


def _scoped_admin_enquiry_lists(
    admin_user,
    *,
    enquiry_type_filter: str | None,
    status_filter: str | None,
    search: str | None,
):
    e_qs = _ho_admin_enquiry_qs(
        _admin_enquiry_scope(Enquiry.objects.all(), admin_user)
    ).select_related("franchise")
    f_qs = _admin_enquiry_scope(FranchiseEnquiry.objects.all(), admin_user).select_related("franchise")

    if enquiry_type_filter == "FRANCHISE":
        e_qs = e_qs.none()
    elif enquiry_type_filter == "ADMISSION":
        e_qs = e_qs.filter(enquiry_type=EnquiryType.ADMISSION)
        f_qs = f_qs.none()
    elif enquiry_type_filter == "CONTACT":
        e_qs = e_qs.filter(enquiry_type=EnquiryType.CONTACT)
        f_qs = f_qs.none()

    status_value = (status_filter or "").strip()
    if status_value and status_value.lower() != "all":
        e_qs = e_qs.filter(status=status_value)
        f_qs = f_qs.filter(status=status_value)

    e_qs = _apply_admin_enquiry_search(e_qs, search)
    f_qs = _apply_admin_enquiry_search(f_qs, search)
    return e_qs.order_by("-created_at"), f_qs.order_by("-created_at")


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


def _paginated_admin_enquiry_response(request, admin_user) -> dict:
    page, limit = _parse_admin_list_params(request)
    params = request.query_params
    enquiry_type = _normalize_admin_type_filter(params.get("type"))
    status_filter = (params.get("status") or "").strip() or None
    search = (params.get("search") or "").strip() or None

    e_qs, f_qs = _scoped_admin_enquiry_lists(
        admin_user,
        enquiry_type_filter=enquiry_type,
        status_filter=status_filter,
        search=search,
    )
    rows: list[tuple] = []
    for obj in e_qs:
        rows.append((obj.created_at, EnquirySerializer(obj).data))
    for obj in f_qs:
        rows.append((obj.created_at, FranchiseEnquiryReadSerializer(obj).data))
    rows.sort(key=lambda row: row[0], reverse=True)
    total = len(rows)
    offset = (page - 1) * limit
    results = [row[1] for row in rows[offset : offset + limit]]
    return {
        "results": results,
        "total": total,
        "page": page,
        "limit": limit,
        "counts": _admin_enquiry_tab_counts(admin_user),
    }


@method_decorator(csrf_exempt, name="dispatch")
class LandingEnquirySubmitView(View):
    """HTML form POST from legacy landing pages → ``kids_enquiry`` + redirect."""

    def post(self, request, *args, **kwargs):
        return handle_landing_enquiry_post(request.POST)


@method_decorator(csrf_exempt, name="dispatch")
class EnquiryCreateView(generics.CreateAPIView):
    serializer_class = EnquirySerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        phone = request.data.get("phone") or request.data.get("mobile")
        email = request.data.get("email")
        enquiry_type = request.data.get("enquiry_type")
        if phone and Enquiry.objects.filter(phone=phone, enquiry_type=enquiry_type).exists():
            return Response(
                {"error": "An enquiry with this phone number has already been submitted for this form."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if email and Enquiry.objects.filter(email=email, enquiry_type=enquiry_type).exists():
            return Response(
                {"error": "An enquiry with this email address has already been submitted for this form."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        enquiry: Enquiry = serializer.save()
        self._send_notifications(enquiry)

    def _send_notifications(self, enquiry: Enquiry) -> None:
        import logging
        import traceback

        logger = logging.getLogger(__name__)

        try:
            from .emails import (
                lead_source_label_for_enquiry,
                send_crm_heads_new_lead_reminder,
                send_enquiry_email,
            )

            email_sent = send_enquiry_email(enquiry)

            if email_sent:
                logger.info(f"Email notification sent for enquiry from {enquiry.name}")
            else:
                logger.warning(f"Failed to send email notification for enquiry from {enquiry.name}")

            send_crm_heads_new_lead_reminder(
                name=enquiry.name or "",
                lead_source=lead_source_label_for_enquiry(enquiry),
            )
        except Exception as e:
            logger.error(f"Error sending enquiry email notification: {str(e)}")
            logger.error(traceback.format_exc())


@method_decorator(csrf_exempt, name="dispatch")
class FranchiseEnquiryCreateView(generics.CreateAPIView):
    serializer_class = FranchiseEnquiryCreateSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        phone = request.data.get("phone") or request.data.get("mobile")
        email = request.data.get("email")
        if phone and FranchiseEnquiry.objects.filter(phone=phone).exists():
            return Response(
                {"error": "A franchise enquiry with this phone number has already been submitted."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if email and FranchiseEnquiry.objects.filter(email=email).exists():
            return Response(
                {"error": "A franchise enquiry with this email address has already been submitted."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        lead: FranchiseEnquiry = serializer.save()
        self._send_notifications(lead)

    def _send_notifications(self, lead: FranchiseEnquiry) -> None:
        import logging
        import traceback

        logger = logging.getLogger(__name__)

        try:
            from .emails import send_crm_heads_new_lead_reminder, send_franchise_enquiry_email

            email_sent = send_franchise_enquiry_email(lead)

            if email_sent:
                logger.info(f"Email notification sent for franchise lead from {lead.name}")
            else:
                logger.warning(f"Failed to send email notification for franchise lead from {lead.name}")

            send_crm_heads_new_lead_reminder(
                name=lead.name or "",
                lead_source="Franchise",
            )
        except Exception as e:
            logger.error(f"Error sending franchise enquiry email notification: {str(e)}")
            logger.error(traceback.format_exc())


class AdminEnquiryListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, *args, **kwargs):
        return Response(_paginated_admin_enquiry_response(request, request.user))


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
        return Response(_paginated_admin_enquiry_response(request, request.user))


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

    def perform_create(self, serializer):
        lead = serializer.save()
        try:
            from .emails import lead_source_label_for_crm_lead, send_crm_heads_new_lead_reminder

            send_crm_heads_new_lead_reminder(
                name=getattr(lead, "full_name", None) or getattr(lead, "name", None) or "",
                lead_source=lead_source_label_for_crm_lead(lead),
            )
        except Exception:
            import logging

            logging.getLogger(__name__).exception("CRM heads reminder failed for CrmLead id=%s", getattr(lead, "pk", None))


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
        from .crm_api import parse_lead_id, unified_lead_detail

        data = unified_lead_detail(pk, include_detail=True, request=request)
        if not data:
            return Response({"message": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(data)

    def patch(self, request, pk):
        if not can_view_crm_leads(request):
            return Response({"detail": "CRM login required."}, status=status.HTTP_403_FORBIDDEN)

        from .crm_api import update_unified_lead

        try:
            data = update_unified_lead(pk, request.data or {}, include_detail=True, request=request)
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


class AdminCrmReportsView(APIView):
    """CRM reports data — pivot table."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not can_view_crm_leads(request):
            return Response(
                {"detail": "CRM login required. Sign in with a CRM account to view CRM reports."},
                status=status.HTTP_403_FORBIDDEN,
            )

        from .crm_api import unified_reports_data

        return Response(unified_reports_data(request))


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

        # Allow notes for all lead types via UnifiedLeadNote
        content = (request.data.get("content") or "").strip()
        if not content:
            return Response({"message": "Note content is required."}, status=status.HTTP_400_BAD_REQUEST)

        from .models import UnifiedLeadNote, CrmLead, Enquiry, FranchiseEnquiry
        from .crm_api import unified_note_to_dict

        status_val = (request.data.get("status") or "").strip()
        if not status_val:
            if kind == "crm":
                lead = CrmLead.objects.filter(pk=numeric_id).first()
                status_val = lead.status if lead else ""
            elif kind == "enquiry":
                lead = Enquiry.objects.filter(pk=numeric_id).first()
                status_val = lead.status if lead else ""
            elif kind == "franchiseenquiry":
                lead = FranchiseEnquiry.objects.filter(pk=numeric_id).first()
                status_val = lead.status if lead else ""

        lead_id = f"{kind}_{numeric_id}"
        note = UnifiedLeadNote.objects.create(lead_id=lead_id, content=content, status=status_val)
        return Response(unified_note_to_dict(note), status=status.HTTP_201_CREATED)


class AdminCrmSendReminderView(APIView):
    """
    CRM reminder / Direct Contact email.
    Email channel sends via SendGrid From franchise@… To the lead.
    WhatsApp remains client-side (returns success for UI compatibility).
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        if not can_view_crm_leads(request):
            return Response({"detail": "CRM login required."}, status=status.HTTP_403_FORBIDDEN)

        channel = (request.data.get("channel") or "email").strip().lower()
        if channel == "whatsapp":
            return Response({"success": True})

        if channel != "email":
            return Response({"error": "Unsupported channel."}, status=status.HTTP_400_BAD_REQUEST)

        lead_id = request.data.get("leadId") or request.data.get("lead_id")
        if not lead_id:
            return Response({"error": "leadId is required."}, status=status.HTTP_400_BAD_REQUEST)

        from .crm_api import unified_lead_detail
        from .emails import crm_direct_from_email, send_crm_direct_contact_email

        lead = unified_lead_detail(str(lead_id), request=request)
        if not lead:
            return Response({"error": "Lead not found."}, status=status.HTTP_404_NOT_FOUND)

        to_email = (lead.get("email") or "").strip()
        if not to_email:
            return Response(
                {"error": "Lead has no email address."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        name = (lead.get("fullName") or lead.get("name") or "there").strip() or "there"
        reminder_type = (request.data.get("type") or "follow-up").strip().lower()
        subject = (request.data.get("subject") or "").strip()
        body = (request.data.get("body") or "").strip()
        if not subject:
            subject = (
                "T.I.M.E. Kids – Meeting reminder"
                if reminder_type == "meeting"
                else "T.I.M.E. Kids – Follow-up"
            )
        if not body:
            body = (
                f"Hi {name},\n\n"
                "This is a reminder from T.I.M.E. Kids regarding your enquiry. "
                "Please let us know a convenient time to connect.\n\n"
                "Best regards,\nT.I.M.E. Kids Team"
            )

        ok = send_crm_direct_contact_email(to_email=to_email, subject=subject, body=body)
        if not ok:
            return Response(
                {"error": "Failed to send email. Check SendGrid configuration."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(
            {
                "success": True,
                "from": crm_direct_from_email(),
                "to": to_email,
            }
        )


class AdminCrmCentresView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not can_view_crm_leads(request):
            return Response({"detail": "CRM login required."}, status=status.HTTP_403_FORBIDDEN)

        from django.db.models import Q
        from django.db.models.functions import Trim

        from franchises.franchise_geo import city_query_variants, filter_queryset_by_city, filter_queryset_by_state
        from franchises.models import Franchise

        qs = Franchise.objects.filter(is_active=True).order_by("name")
        city = (request.query_params.get("city") or "").strip()
        state = (request.query_params.get("state") or "").strip()

        if city:
            cities = [c.strip() for c in city.split(",") if c.strip()]
            if len(cities) == 1:
                qs = filter_queryset_by_city(qs, cities[0])
            elif cities:
                q = Q()
                for name in cities:
                    for variant in city_query_variants(name):
                        q |= Q(city_trim__iexact=variant) | Q(cityname_trim__iexact=variant)
                qs = qs.annotate(
                    city_trim=Trim("city"),
                    cityname_trim=Trim("cityname"),
                ).filter(q)
        elif state:
            states = [s.strip() for s in state.split(",") if s.strip()]
            if len(states) == 1:
                qs = filter_queryset_by_state(qs, states[0])
            elif states:
                matched_ids = set()
                for st in states:
                    matched_ids.update(
                        filter_queryset_by_state(
                            Franchise.objects.filter(is_active=True),
                            st,
                        ).values_list("id", flat=True)
                    )
                qs = qs.filter(id__in=matched_ids)

        from accounts.crm_zones import filter_franchise_qs_by_zone

        qs = filter_franchise_qs_by_zone(qs, request)

        centres = [{"id": str(f.id), "name": f.name} for f in qs]
        return Response(centres)


class AdminCrmCitiesView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not can_view_crm_leads(request):
            return Response({"detail": "CRM login required."}, status=status.HTTP_403_FORBIDDEN)

        from .crm_api import unified_crm_cities

        state = request.query_params.get("state")
        cities = unified_crm_cities(state, request=request)
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

class LeadNoteListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, lead_id):
        from .models import UnifiedLeadNote
        notes = UnifiedLeadNote.objects.filter(lead_id=lead_id).order_by('created_at')
        return Response([
            {
                "id": n.id,
                "content": n.content,
                "created_at": n.created_at.isoformat()
            } for n in notes
        ])

    def post(self, request, lead_id):
        from .models import UnifiedLeadNote
        content = (request.data.get("content") or "").strip()
        if not content:
            return Response({"message": "Content is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        note = UnifiedLeadNote.objects.create(lead_id=lead_id, content=content)
        return Response({
            "id": note.id,
            "content": note.content,
            "created_at": note.created_at.isoformat()
        }, status=status.HTTP_201_CREATED)


class AdminCrmStatesView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not can_view_crm_leads(request):
            return Response({"detail": "CRM login required."}, status=status.HTTP_403_FORBIDDEN)

        from franchises.franchise_geo import state_to_display
        from franchises.models import Franchise
        from enquiries.models import FranchiseEnquiry
        from accounts.crm_zones import request_scope_state_codes, scope_display_state_names

        codes = request_scope_state_codes(request)
        # Scoped CRM (zone or region): return the full state list for that scope.
        if codes is not None:
            return Response([{"name": name} for name in scope_display_state_names(codes)])

        states = set()
        for s in FranchiseEnquiry.objects.exclude(state__isnull=True).exclude(state="").values_list("state", flat=True).distinct():
            display = state_to_display(s) or s.strip().title()
            if display:
                states.add(display)
        for s in Franchise.objects.exclude(state__isnull=True).exclude(state="").values_list("state", flat=True).distinct():
            display = state_to_display(s) or s.strip().title()
            if display:
                states.add(display)
        for s in Franchise.objects.exclude(statename__isnull=True).exclude(statename="").values_list("statename", flat=True).distinct():
            display = state_to_display(s) or s.strip().title()
            if display:
                states.add(display)

        return Response([{"name": name} for name in sorted(list(states), key=str.casefold)])
