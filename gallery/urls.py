from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import GallerySectionViewSet, MediaItemViewSet

router = DefaultRouter()
router.register(r"sections", GallerySectionViewSet, basename="gallery-sections")
router.register(r"", MediaItemViewSet, basename="media-items")

urlpatterns = [
    path("", include(router.urls)),
]
