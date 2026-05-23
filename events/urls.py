from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminEventViewSet,
    EventMediaListCreateView,
    EventMediaDetailView,
    FranchiseEventViewSet,
    ParentEventListView,
    PublicEventListView,
    event_media_file,
    public_event_media_file,
)

router = DefaultRouter()
router.register("admin", AdminEventViewSet, basename="admin-events")
router.register("franchise", FranchiseEventViewSet, basename="franchise-events")

urlpatterns = router.urls + [
    path("media/<int:pk>/file/", event_media_file, name="event-media-file"),
    path("franchise/<int:event_id>/media/", EventMediaListCreateView.as_view(), name="event-media-list"),
    path("franchise/<int:event_id>/media/<int:pk>/", EventMediaDetailView.as_view(), name="event-media-detail"),
    path("parent/", ParentEventListView.as_view(), name="parent-events"),
    path("public/<slug:slug>/", PublicEventListView.as_view(), name="public-events"),
    path(
        "public/<slug:slug>/media/<int:pk>/file/",
        public_event_media_file,
        name="public-event-media-file",
    ),
]
