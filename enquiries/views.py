from django.conf import settings
from django.core.mail import send_mail
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
        subject = f"{enquiry.enquiry_type.title()} enquiry from {enquiry.name}"
        message_lines = [
            f"Name: {enquiry.name}",
            f"Email: {enquiry.email}",
            f"Phone: {enquiry.phone}",
            f"City: {enquiry.city}",
            f"Message: {enquiry.message}",
        ]
        if enquiry.child_age:
            message_lines.append(f"Child age: {enquiry.child_age}")
        if enquiry.franchise:
            message_lines.append(f"Franchise: {enquiry.franchise.name}")
        message = "\n".join(message_lines)

        recipients = [settings.DEFAULT_FROM_EMAIL]
        if enquiry.franchise and enquiry.franchise.contact_email:
            recipients.append(enquiry.franchise.contact_email)
        if enquiry.franchise and enquiry.franchise.admin.email:
            recipients.append(enquiry.franchise.admin.email)

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=list({r for r in recipients if r}),
            fail_silently=True,
        )


class AdminEnquiryListView(generics.ListAPIView):
    serializer_class = EnquirySerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
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
