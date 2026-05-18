from django.db.models import Q
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from accounts.permissions import IsAdminOrApproverUser
from .models import GallerySection, MediaItem
from .serializers import GallerySectionSerializer, MediaItemSerializer


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 500


class GallerySectionViewSet(viewsets.ModelViewSet):
    """Admin CMS: gallery headings (albums on /gallery)."""

    queryset = GallerySection.objects.all().order_by("order", "title")
    serializer_class = GallerySectionSerializer
    permission_classes = [IsAdminOrApproverUser]
    pagination_class = None


class MediaItemViewSet(viewsets.ModelViewSet):
    queryset = MediaItem.objects.select_related("section").order_by("order", "-id")
    serializer_class = MediaItemSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsSetPagination

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def get_queryset(self):
        qs = MediaItem.objects.select_related("section").order_by("order", "-id")
        if self.request.method in ("GET", "HEAD"):
            section_id = self.request.query_params.get("section")
            if section_id:
                qs = qs.filter(section_id=section_id)
            category = self.request.query_params.get("category")
            if category:
                qs = qs.filter(category=category)
            # Public list: only items under an active gallery heading (Photo/Video Gallery CMS).
            if not self.request.user or not self.request.user.is_authenticated:
                qs = qs.exclude(category="Banner").filter(
                    section__isnull=False,
                    section__is_active=True,
                )
        return qs

    def perform_destroy(self, instance):
        if instance.file:
            instance.file.delete(save=False)
        super().perform_destroy(instance)
