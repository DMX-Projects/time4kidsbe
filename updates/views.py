from rest_framework import viewsets
from rest_framework import generics
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied
from .models import Update, SocialMediaUpload
from .serializers import UpdateSerializer, SocialMediaUploadSerializer
from accounts.permissions import IsFranchiseUser, IsAdminUser

class UpdateViewSet(viewsets.ModelViewSet):
    queryset = Update.objects.all()
    serializer_class = UpdateSerializer
    permission_classes = [AllowAny] # Ideally should be IsAuthenticated for write, AllowAny for read

    def get_queryset(self):
        queryset = Update.objects.all().order_by('-start_date')
        
        # Filter by franchise slug (for public school page)
        franchise_slug = self.request.query_params.get('franchise_slug')
        if franchise_slug:
            queryset = queryset.filter(franchise__slug=franchise_slug, is_active=True)
            return queryset

        # Filter by logged-in user's franchise (for dashboard)
        user = self.request.user
        if user.is_authenticated and hasattr(user, 'franchise_profile'):
             return queryset.filter(franchise=user.franchise_profile)
        
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_authenticated and hasattr(user, 'franchise_profile'):
            serializer.save(franchise=user.franchise_profile)
        else:
             # Fallback for testing/admin if needed, or raise error
             serializer.save()


class FranchiseSocialMediaUploadListCreateView(generics.ListCreateAPIView):
    """Franchise users upload images/videos; items start as `pending`."""

    serializer_class = SocialMediaUploadSerializer
    permission_classes = [IsFranchiseUser]

    def get_queryset(self):
        franchise_profile = getattr(self.request.user, "franchise_profile", None)
        if not franchise_profile:
            return SocialMediaUpload.objects.none()
        return SocialMediaUpload.objects.filter(franchise=franchise_profile).order_by("-created_at")

    def perform_create(self, serializer):
        franchise_profile = getattr(self.request.user, "franchise_profile", None)
        if not franchise_profile:
            raise PermissionDenied("Franchise profile not found")
        serializer.save(franchise=franchise_profile)


class AdminSocialMediaUploadListView(generics.ListAPIView):
    """Admin lists all uploads and can review by status."""

    serializer_class = SocialMediaUploadSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        status = self.request.query_params.get("status")
        qs = SocialMediaUpload.objects.all().order_by("-created_at")
        if status:
            qs = qs.filter(status=status)
        return qs


class AdminSocialMediaUploadUpdateView(generics.UpdateAPIView):
    """Admin approves/rejects uploads by PATCHing status and notes."""

    serializer_class = SocialMediaUploadSerializer
    permission_classes = [IsAdminUser]
    queryset = SocialMediaUpload.objects.all().order_by("-created_at")
