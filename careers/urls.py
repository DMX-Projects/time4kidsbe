from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminCareerViewSet,
    PublicCareerListView,
    PublicJobApplicationCreateView,
    AdminJobApplicationViewSet,
)

router = DefaultRouter()
router.register("admin", AdminCareerViewSet, basename="admin-career")
router.register("admin/applications", AdminJobApplicationViewSet, basename="admin-application")

urlpatterns = router.urls + [
    path("public/", PublicCareerListView.as_view(), name="public-careers"),
    path("applications/", PublicJobApplicationCreateView.as_view(), name="job-application"),
]
