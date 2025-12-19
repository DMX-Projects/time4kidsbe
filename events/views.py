from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, viewsets
from rest_framework.exceptions import PermissionDenied

from accounts.permissions import IsAdminUser, IsFranchiseUser, IsParentUser
from franchises.models import Franchise
from .models import Event, EventMedia
from .serializers import EventMediaSerializer, EventSerializer


class AdminEventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return Event.objects.select_related("franchise").filter(franchise__admin=self.request.user)

    def perform_create(self, serializer):
        franchise_id = self.request.data.get("franchise")
        franchise = get_object_or_404(Franchise, pk=franchise_id, admin=self.request.user)
        serializer.save(franchise=franchise, created_by=self.request.user)

    def perform_update(self, serializer):
        franchise_id = self.request.data.get("franchise") or None
        franchise = None
        if franchise_id:
            franchise = get_object_or_404(Franchise, pk=franchise_id, admin=self.request.user)
        serializer.save(franchise=franchise or serializer.instance.franchise)


class FranchiseEventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsFranchiseUser]

    def get_queryset(self):
        franchise = getattr(self.request.user, "franchise_profile", None)
        if not franchise:
            return Event.objects.none()
        return Event.objects.filter(franchise=franchise)

    def perform_create(self, serializer):
        franchise = getattr(self.request.user, "franchise_profile", None)
        if not franchise:
            raise PermissionDenied("Franchise profile not found for this user")
        serializer.save(franchise=franchise, created_by=self.request.user)

    def perform_update(self, serializer):
        franchise = getattr(self.request.user, "franchise_profile", None)
        if not franchise:
            raise PermissionDenied("Franchise profile not found for this user")
        serializer.save(franchise=franchise)

    def perform_destroy(self, instance):
        franchise = getattr(self.request.user, "franchise_profile", None)
        if instance.franchise != franchise:
            raise PermissionDenied("Cannot delete events outside your franchise")
        instance.delete()


class EventMediaListCreateView(generics.ListCreateAPIView):
    serializer_class = EventMediaSerializer
    permission_classes = [IsFranchiseUser]

    def get_queryset(self):
        event = get_object_or_404(Event, pk=self.kwargs["event_id"])
        franchise = getattr(self.request.user, "franchise_profile", None)
        if event.franchise != franchise:
            raise PermissionDenied("Cannot view media for another franchise")
        return EventMedia.objects.filter(event=event)

    def perform_create(self, serializer):
        event = get_object_or_404(Event, pk=self.kwargs["event_id"])
        franchise = getattr(self.request.user, "franchise_profile", None)
        if event.franchise != franchise:
            raise PermissionDenied("Cannot add media to another franchise")
        serializer.save(event=event, uploaded_by=self.request.user)


class ParentEventListView(generics.ListAPIView):
    serializer_class = EventSerializer
    permission_classes = [IsParentUser]

    def get_queryset(self):
        parent_profile = getattr(self.request.user, "parent_profile", None)
        if not parent_profile:
            return Event.objects.none()
        return Event.objects.filter(franchise=parent_profile.franchise)


class PublicEventListView(generics.ListAPIView):
    serializer_class = EventSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        franchise = get_object_or_404(Franchise, slug=self.kwargs["slug"], is_active=True)
        return Event.objects.filter(franchise=franchise)
