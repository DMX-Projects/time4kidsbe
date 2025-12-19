from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AdminCareerViewSet, PublicCareerListView

router = DefaultRouter()
router.register("admin", AdminCareerViewSet, basename="admin-career")

urlpatterns = router.urls + [
    path("public/", PublicCareerListView.as_view(), name="public-careers"),
]
