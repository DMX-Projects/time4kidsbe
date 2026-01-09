from rest_framework import generics, permissions, viewsets

from accounts.permissions import IsAdminUser
from .models import Career, JobApplication
from .serializers import CareerSerializer, JobApplicationSerializer


class AdminCareerViewSet(viewsets.ModelViewSet):
    serializer_class = CareerSerializer
    permission_classes = [IsAdminUser]
    queryset = Career.objects.all()

    def get_queryset(self):
        return self.queryset.filter(admin=self.request.user)

    def perform_create(self, serializer):
        serializer.save(admin=self.request.user)


class PublicCareerListView(generics.ListAPIView):
    serializer_class = CareerSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Career.objects.filter(is_active=True)


class PublicJobApplicationCreateView(generics.CreateAPIView):
    """Public endpoint for candidates to submit job applications"""
    serializer_class = JobApplicationSerializer
    permission_classes = [permissions.AllowAny]
    queryset = JobApplication.objects.all()
    
    def perform_create(self, serializer):
        """Save application and send email notification"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Save the application first
        application = serializer.save()
        print(f"✅ Application saved: {application.full_name} for {application.career.title}")
        logger.info(f"Application saved: {application.full_name} for {application.career.title}")
        
        # Try to send email notification (don't fail if this fails)
        try:
            print("📧 Attempting to send email...")
            from .emails import send_career_application_email
            print("✅ Email module imported successfully")
            email_sent = send_career_application_email(application)
            print(f"📧 Email send result: {email_sent}")
            if email_sent:
                print(f"✅ Email notification sent successfully!")
                logger.info(f"Email notification sent for application by {application.full_name}")
            else:
                print(f"❌ Email sending returned False")
                logger.warning(f"Failed to send email notification for application by {application.full_name}")
        except ImportError as e:
            print(f"❌ Could not import email module: {str(e)}")
            logger.error(f"Could not import email module: {str(e)}")
        except Exception as e:
            # Log error but don't fail the application submission
            print(f"❌ Error sending email: {str(e)}")
            logger.error(f"Error sending email notification: {str(e)}")
            import traceback
            print(traceback.format_exc())
            logger.error(traceback.format_exc())




class AdminJobApplicationViewSet(viewsets.ModelViewSet):
    """Admin endpoint to view and manage job applications"""
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAdminUser]
    queryset = JobApplication.objects.all()

    def get_queryset(self):
        # Show applications for careers created by this admin
        return self.queryset.filter(career__admin=self.request.user)
