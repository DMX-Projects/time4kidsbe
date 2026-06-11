import mimetypes
import re
from pathlib import Path

from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, viewsets
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated

from accounts.models import UserRole
from accounts.permissions import IsAdminUser, IsFranchiseUser, IsParentUser
from accounts.profile_access import franchise_profile_for_user, parent_profile_for_user
from documents.auth import QueryJWTAuthentication
from documents.download_names import safe_disposition_filename
from franchises.models import Franchise
from .models import Event, EventMedia
from .serializers import EventMediaSerializer, EventSerializer
from .visibility import parent_events_queryset


def _norm_user_role(user) -> str:
    return str(getattr(user, "role", "") or "").strip().upper()


def _event_media_fallback_filename(media: EventMedia) -> str:
    stored = Path(media.file.name).name if media.file else ""
    ext = Path(stored).suffix if stored else ""
    base = (media.caption or "").strip() or (Path(stored).stem if stored else "media")
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", base)
    safe = re.sub(r"\s+", " ", safe).strip().strip(".") or "media"
    if ext and not safe.lower().endswith(ext.lower()):
        safe = f"{safe}{ext}"
    return safe


def _user_can_stream_event_media(user, media: EventMedia) -> bool:
    event = media.event
    role = _norm_user_role(user)
    if role == UserRole.PARENT.value:
        profile = parent_profile_for_user(user)
        return profile is not None and event.franchise_id == profile.franchise_id
    if role == UserRole.FRANCHISE.value:
        franchise = franchise_profile_for_user(user)
        return franchise is not None and event.franchise_id == franchise.id
    return False


def _stream_event_media_response(media: EventMedia, request) -> FileResponse:
    if not media.file:
        raise Http404("No file on this record.")
    try:
        file_handle = media.file.open("rb")
    except FileNotFoundError:
        raise Http404("File missing on server.") from None
    stored_name = getattr(media.file, "name", "") or ""
    content_type, _encoding = mimetypes.guess_type(stored_name)
    if not content_type:
        content_type = "application/octet-stream"
    fallback = _event_media_fallback_filename(media)
    filename = safe_disposition_filename(request.GET.get("name"), fallback)
    return FileResponse(
        file_handle,
        as_attachment=False,
        content_type=content_type,
        filename=filename,
    )


@api_view(["GET"])
@authentication_classes([QueryJWTAuthentication])
@permission_classes([IsAuthenticated])
def event_media_file(request, pk: int):
    """
    Stream event media (photo/video) with JWT in header or ?access= so dashboards
    do not rely on public /media/… on the marketing domain.
    """
    media = get_object_or_404(EventMedia.objects.select_related("event"), pk=pk)
    if not _user_can_stream_event_media(request.user, media):
        raise PermissionDenied("You do not have access to this media.")
    return _stream_event_media_response(media, request)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def public_event_media_file(request, slug: str, pk: int):
    """Public centre “Life at …” gallery — active franchise only."""
    franchise = get_object_or_404(Franchise, slug=slug, is_active=True)
    media = get_object_or_404(
        EventMedia.objects.select_related("event"),
        pk=pk,
        event__franchise=franchise,
    )
    return _stream_event_media_response(media, request)


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
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return Event.objects.none()
        return Event.objects.filter(franchise=franchise).prefetch_related("media")

    def perform_create(self, serializer):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            raise PermissionDenied("Franchise profile not found for this user")
        serializer.save(franchise=franchise, created_by=self.request.user)

    def perform_update(self, serializer):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            raise PermissionDenied("Franchise profile not found for this user")
        serializer.save(franchise=franchise)

    def perform_destroy(self, instance):
        franchise = franchise_profile_for_user(self.request.user)
        if instance.franchise != franchise:
            raise PermissionDenied("Cannot delete events outside your franchise")
        instance.delete()


class EventMediaListCreateView(generics.ListCreateAPIView):
    serializer_class = EventMediaSerializer
    permission_classes = [IsFranchiseUser]

    def get_queryset(self):
        event = get_object_or_404(Event, pk=self.kwargs["event_id"])
        franchise = franchise_profile_for_user(self.request.user)
        if event.franchise != franchise:
            raise PermissionDenied("Cannot view media for another franchise")
        return EventMedia.objects.filter(event=event)

    def perform_create(self, serializer):
        event = get_object_or_404(Event, pk=self.kwargs["event_id"])
        franchise = franchise_profile_for_user(self.request.user)
        if event.franchise != franchise:
            raise PermissionDenied("Cannot add media to another franchise")
        serializer.save(event=event, uploaded_by=self.request.user)


class EventMediaDetailView(generics.RetrieveUpdateDestroyAPIView):
    """View for retrieving, updating and deleting individual event media items."""
    serializer_class = EventMediaSerializer
    permission_classes = [IsFranchiseUser]

    def get_queryset(self):
        event = get_object_or_404(Event, pk=self.kwargs["event_id"])
        franchise = franchise_profile_for_user(self.request.user)
        if event.franchise != franchise:
            raise PermissionDenied("Cannot access media for another franchise")
        return EventMedia.objects.filter(event=event)

    def perform_update(self, serializer):
        # Ensure the media belongs to the franchise's event
        event = get_object_or_404(Event, pk=self.kwargs["event_id"])
        franchise = franchise_profile_for_user(self.request.user)
        if event.franchise != franchise:
            raise PermissionDenied("Cannot update media for another franchise")
        serializer.save()

    def perform_destroy(self, instance):
        # Ensure the media belongs to the franchise's event
        event = get_object_or_404(Event, pk=self.kwargs["event_id"])
        franchise = franchise_profile_for_user(self.request.user)
        if event.franchise != franchise:
            raise PermissionDenied("Cannot delete media for another franchise")
        instance.delete()


class ParentEventListView(generics.ListAPIView):
    serializer_class = EventSerializer
    permission_classes = [IsParentUser]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["omit_video_links"] = True
        return ctx

    def get_queryset(self):
        parent_profile = parent_profile_for_user(self.request.user)
        return parent_events_queryset(parent_profile)


class PublicEventListView(generics.ListAPIView):
    serializer_class = EventSerializer
    permission_classes = [permissions.AllowAny]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["omit_video_links"] = True
        return ctx

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["omit_video_links"] = True
        return ctx

    def get_queryset(self):
        franchise = get_object_or_404(Franchise, slug=self.kwargs["slug"], is_active=True)
        return Event.objects.filter(franchise=franchise).prefetch_related("media").order_by(
            "-start_date", "-created_at"
        )
