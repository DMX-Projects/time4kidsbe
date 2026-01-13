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
        # Return all enquiries for superusers or staff
        if self.request.user.is_superuser or self.request.user.is_staff:
            return Enquiry.objects.all()
        # Fallback for other users (e.g. franchise admins if they use this endpoint, although they have their own)
        return Enquiry.objects.filter(franchise__admin=self.request.user)


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
        qs = Enquiry.objects.all()
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
