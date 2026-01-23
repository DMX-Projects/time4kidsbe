from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AdminEventViewSet, EventMediaListCreateView, EventMediaDetailView, FranchiseEventViewSet, ParentEventListView, PublicEventListView

router = DefaultRouter()
router.register("admin", AdminEventViewSet, basename="admin-events")
router.register("franchise", FranchiseEventViewSet, basename="franchise-events")

urlpatterns = router.urls + [
    path("franchise/<int:event_id>/media/", EventMediaListCreateView.as_view(), name="event-media-list"),
    path("franchise/<int:event_id>/media/<int:pk>/", EventMediaDetailView.as_view(), name="event-media-detail"),
    path("parent/", ParentEventListView.as_view(), name="parent-events"),
    path("public/<slug:slug>/", PublicEventListView.as_view(), name="public-events"),
]
