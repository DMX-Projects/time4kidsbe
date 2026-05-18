from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminUser, IsFranchiseUser
from accounts.profile_access import franchise_profile_for_user

from .landing_submit import handle_landing_enquiry_post
from .models import Enquiry, FranchiseEnquiry
from .serializers import (
    EnquirySerializer,
    FranchiseEnquiryCreateSerializer,
    FranchiseEnquiryReadSerializer,
    FranchiseEnquiryStatusSerializer,
)


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
class LandingEnquirySubmitView(APIView):
    """HTML form POST from legacy landing pages → ``kids_enquiry`` + redirect."""

    permission_classes = [permissions.AllowAny]

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


class EnquiryUpdateView(generics.UpdateAPIView):
    serializer_class = EnquirySerializer
    permission_classes = [IsAdminUser]
    queryset = Enquiry.objects.all()
    lookup_field = "pk"


class FranchiseEnquiryUpdateView(generics.UpdateAPIView):
    serializer_class = EnquirySerializer
    permission_classes = [IsFranchiseUser]
    lookup_field = "pk"

    def get_queryset(self):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return Enquiry.objects.none()
        return Enquiry.objects.filter(franchise=franchise)


class FranchiseLeadAdminUpdateView(generics.UpdateAPIView):
    serializer_class = FranchiseEnquiryStatusSerializer
    permission_classes = [IsAdminUser]
    lookup_field = "pk"
    http_method_names = ["patch", "put", "head", "options"]

    def get_queryset(self):
        admin_user = self.request.user
        return FranchiseEnquiry.objects.filter(
            Q(franchise__isnull=True) | Q(franchise__admin=admin_user)
        ).select_related("franchise")


class FranchiseLeadPartnerUpdateView(generics.UpdateAPIView):
    serializer_class = FranchiseEnquiryStatusSerializer
    permission_classes = [IsFranchiseUser]
    lookup_field = "pk"
    http_method_names = ["patch", "put", "head", "options"]

    def get_queryset(self):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return FranchiseEnquiry.objects.none()
        return FranchiseEnquiry.objects.filter(franchise=franchise).select_related("franchise")
