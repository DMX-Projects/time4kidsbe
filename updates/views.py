from rest_framework import generics, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied

from accounts.models import UserRole
from accounts.permissions import IsFranchiseUser, IsAdminOrApproverUser
from accounts.profile_access import franchise_profile_for_user as _franchise_profile_for_user

from .models import SocialMediaUpload, Update
from .serializers import SocialMediaUploadSerializer, UpdateSerializer


class UpdateViewSet(viewsets.ModelViewSet):
    queryset = Update.objects.select_related("franchise").all()
    serializer_class = UpdateSerializer
    permission_classes = [AllowAny]  # Ideally should be IsAuthenticated for write, AllowAny for read

    def get_queryset(self):
        queryset = Update.objects.select_related("franchise").all().order_by("-start_date")

        franchise_slug = self.request.query_params.get("franchise_slug")
        if franchise_slug:
            return queryset.filter(franchise__slug=franchise_slug, is_active=True)

        user = self.request.user
        profile = _franchise_profile_for_user(user)
        if profile is not None:
            return queryset.filter(franchise=profile)

        if user.is_authenticated and getattr(user, "role", None) in (UserRole.ADMIN, UserRole.APPROVER):
            return queryset

        return queryset.filter(franchise__isnull=True, is_active=True)

    def perform_create(self, serializer):
        user = self.request.user
        profile = _franchise_profile_for_user(user)
        if profile is not None:
            serializer.save(franchise=profile)
        else:
            serializer.save()


class FranchiseSocialMediaUploadListCreateView(generics.ListCreateAPIView):
    """Franchise users upload images/videos; items start as `pending`."""

    serializer_class = SocialMediaUploadSerializer
    permission_classes = [IsFranchiseUser]

    def get_queryset(self):
        profile = _franchise_profile_for_user(self.request.user)
        if not profile:
            return SocialMediaUpload.objects.none()
        return SocialMediaUpload.objects.filter(franchise=profile).select_related("franchise").order_by("-created_at")

    def perform_create(self, serializer):
        profile = _franchise_profile_for_user(self.request.user)
        if not profile:
            raise PermissionDenied("Franchise profile not found")
        serializer.save(franchise=profile)


class AdminSocialMediaUploadListView(generics.ListAPIView):
    """Admin lists all uploads and can review by status."""

    serializer_class = SocialMediaUploadSerializer
    permission_classes = [IsAdminOrApproverUser]

    def get_queryset(self):
        status = self.request.query_params.get("status")
        qs = SocialMediaUpload.objects.select_related("franchise").all().order_by("-created_at")
        if status:
            qs = qs.filter(status=status)
        return qs


class AdminSocialMediaUploadUpdateView(generics.UpdateAPIView):
    """Admin approves/rejects uploads by PATCHing status and notes."""

    serializer_class = SocialMediaUploadSerializer
    permission_classes = [IsAdminOrApproverUser]

    def get_queryset(self):
        return SocialMediaUpload.objects.select_related("franchise").all().order_by("-created_at")
