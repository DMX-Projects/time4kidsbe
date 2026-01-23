from django.conf import settings
from rest_framework import generics, permissions

from accounts.permissions import IsAdminUser, IsFranchiseUser
from .models import Enquiry, EnquiryType
from .serializers import EnquirySerializer


class EnquiryCreateView(generics.CreateAPIView):
    serializer_class = EnquirySerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        enquiry: Enquiry = serializer.save()
        self._send_notifications(enquiry)

    def _send_notifications(self, enquiry: Enquiry) -> None:
        """Send email notification for new enquiry using SendGrid"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            from .emails import send_enquiry_email
            email_sent = send_enquiry_email(enquiry)
            
            if email_sent:
                logger.info(f"Email notification sent for enquiry from {enquiry.name}")
            else:
                logger.warning(f"Failed to send email notification for enquiry from {enquiry.name}")
        except Exception as e:
            # Log error but don't fail the enquiry submission
            logger.error(f"Error sending enquiry email notification: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())


class AdminEnquiryListView(generics.ListAPIView):
    serializer_class = EnquirySerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        # Admin should only see global enquiries (no franchise linked)
        # This prevents seeing duplicates that are assigned to franchises
        return Enquiry.objects.filter(franchise__isnull=True)


class FranchiseEnquiryListView(generics.ListAPIView):
    serializer_class = EnquirySerializer
    permission_classes = [IsFranchiseUser]

    def get_queryset(self):
        franchise = getattr(self.request.user, "franchise_profile", None)
        if not franchise:
            return Enquiry.objects.none()
        return Enquiry.objects.filter(franchise=franchise)


class AdminAllEnquiryListView(generics.ListAPIView):
    serializer_class = EnquirySerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        # Admin should only see global enquiries (no franchise linked)
        qs = Enquiry.objects.filter(franchise__isnull=True)
        enquiry_type = self.request.query_params.get("type")
        if enquiry_type:
            qs = qs.filter(enquiry_type=enquiry_type)
        return qs.order_by("-created_at")


class EnquiryUpdateView(generics.UpdateAPIView):
    """Allow admins to update enquiry status."""
    serializer_class = EnquirySerializer
    permission_classes = [IsAdminUser]
    queryset = Enquiry.objects.all()
    lookup_field = 'pk'
