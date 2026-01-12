from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminFranchiseViewSet,
    AdminFranchiseLocationViewSet,
    AdminParentListView,
    FranchiseLocationViewSet,
    FranchiseParentViewSet,
    FranchiseProfileView,
    PublicFranchiseListView,
    PublicFranchiseDetailView,
    PublicLocationListView,
    state_choices_view,
)

router = DefaultRouter()
router.register("admin/franchises", AdminFranchiseViewSet, basename="admin-franchise")
router.register("admin/franchise-locations", AdminFranchiseLocationViewSet, basename="admin-franchise-locations")
router.register("franchise/parents", FranchiseParentViewSet, basename="franchise-parents")
router.register("franchise-locations", FranchiseLocationViewSet, basename="franchise-locations")

urlpatterns = router.urls + [
    path("franchise/profile/", FranchiseProfileView.as_view(), name="franchise-profile"),
    path("admin/parents/", AdminParentListView.as_view(), name="admin-parent-list"),
    path("public/locations/", PublicLocationListView.as_view(), name="public-franchise-locations"),
    path("public/", PublicFranchiseListView.as_view(), name="public-franchise-list"),
    path("public/<slug:slug>/", PublicFranchiseDetailView.as_view(), name="public-franchise"),
    path("state-choices/", state_choices_view, name="state-choices"),
]
