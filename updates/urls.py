from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UpdateViewSet,
    FranchiseSocialMediaUploadListCreateView,
    AdminSocialMediaUploadListView,
    AdminSocialMediaUploadUpdateView,
)

router = DefaultRouter()
router.register(r"", UpdateViewSet)

# Register concrete paths BEFORE the router. Otherwise `social-media/` is captured as
# UpdateViewSet detail with pk="social-media" and the franchise social upload API never runs.
urlpatterns = [
    path("social-media/admin/<int:pk>/", AdminSocialMediaUploadUpdateView.as_view(), name="social-media-upload-admin-update"),
    path("social-media/admin/", AdminSocialMediaUploadListView.as_view(), name="social-media-upload-admin-list"),
    path("social-media/", FranchiseSocialMediaUploadListCreateView.as_view(), name="social-media-upload-list-create"),
    path("", include(router.urls)),
]
