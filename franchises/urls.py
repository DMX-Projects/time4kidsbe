from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminFranchiseViewSet,
    AdminParentListView,
    FranchiseParentViewSet,
    FranchiseProfileView,
    PublicFranchiseListView,
    PublicFranchiseDetailView,
    PublicLocationListView,
)

router = DefaultRouter()
router.register("admin/franchises", AdminFranchiseViewSet, basename="admin-franchise")
router.register("franchise/parents", FranchiseParentViewSet, basename="franchise-parents")

urlpatterns = router.urls + [
    path("franchise/profile/", FranchiseProfileView.as_view(), name="franchise-profile"),
    path("admin/parents/", AdminParentListView.as_view(), name="admin-parent-list"),
    path("public/locations/", PublicLocationListView.as_view(), name="public-franchise-locations"),
    path("public/", PublicFranchiseListView.as_view(), name="public-franchise-list"),
    path("public/<slug:slug>/", PublicFranchiseDetailView.as_view(), name="public-franchise"),
]
