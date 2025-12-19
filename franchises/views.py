from django.db.models import Count
from rest_framework import generics, permissions, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from accounts.permissions import IsAdminUser, IsFranchiseUser
from .models import Franchise, ParentProfile
from .serializers import (
    FranchiseCreateSerializer,
    FranchiseProfileSerializer,
    FranchiseSerializer,
    FranchiseUpdateSerializer,
    ParentSerializer,
    PublicFranchiseSerializer,
)


class AdminFranchiseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = Franchise.objects.select_related("admin", "user")

    def get_queryset(self):
        # Single-admin setup: return all franchises for the admin to view/edit/delete
        return self.queryset

    def get_serializer_class(self):
        if self.action == "create":
            return FranchiseCreateSerializer
        if self.action in ["update", "partial_update"]:
            return FranchiseUpdateSerializer
        return FranchiseSerializer

    def perform_create(self, serializer):
        serializer.save(admin=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

    def perform_destroy(self, instance):
        if instance.admin != self.request.user:
            raise PermissionDenied("You cannot delete franchises you do not own")
        instance.delete()


class FranchiseProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = FranchiseProfileSerializer
    permission_classes = [IsFranchiseUser]

    def get_object(self):
        franchise = getattr(self.request.user, "franchise_profile", None)
        if not franchise:
            raise PermissionDenied("Franchise profile not found")
        return franchise


class FranchiseParentViewSet(viewsets.ModelViewSet):
    serializer_class = ParentSerializer
    permission_classes = [IsFranchiseUser]
    queryset = ParentProfile.objects.select_related("user", "franchise")

    def get_queryset(self):
        franchise = getattr(self.request.user, "franchise_profile", None)
        if not franchise:
            return ParentProfile.objects.none()
        return self.queryset.filter(franchise=franchise)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["franchise"] = getattr(self.request.user, "franchise_profile", None)
        return context

    def perform_destroy(self, instance):
        franchise = getattr(self.request.user, "franchise_profile", None)
        if instance.franchise != franchise:
            raise PermissionDenied("Cannot delete parent outside your franchise")
        instance.user.delete()


class AdminParentListView(generics.ListAPIView):
    serializer_class = ParentSerializer
    permission_classes = [IsAdminUser]
    queryset = ParentProfile.objects.select_related("user", "franchise")

    def get_queryset(self):
        return self.queryset.filter(franchise__admin=self.request.user)


class PublicFranchiseDetailView(generics.RetrieveAPIView):
    serializer_class = PublicFranchiseSerializer
    lookup_field = "slug"
    permission_classes = [permissions.AllowAny]
    queryset = Franchise.objects.filter(is_active=True).prefetch_related("events__media")


class PublicFranchiseListView(generics.ListAPIView):
    serializer_class = PublicFranchiseSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Franchise.objects.filter(is_active=True).prefetch_related("events__media")

    def get_queryset(self):
        qs = self.queryset
        city = self.request.query_params.get("city")
        state = self.request.query_params.get("state")
        if city:
            qs = qs.filter(city__icontains=city)
        if state:
            qs = qs.filter(state__icontains=state)
        return qs


class PublicLocationListView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        qs = Franchise.objects.filter(is_active=True)
        locations = (
            qs.values("city", "state", "country")
            .annotate(franchise_count=Count("id"))
            .order_by("city")
        )
        payload = [
            {
                "city": loc.get("city", ""),
                "state": loc.get("state", ""),
                "country": loc.get("country", ""),
                "franchise_count": loc["franchise_count"],
            }
            for loc in locations
        ]
        return Response(payload)
