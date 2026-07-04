from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path, re_path
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import RedirectView

from accounts.views import (
    CheckParentEmailView,
    ContentAdminLoginView,
    CrmLoginView,
    CurrentUserView,
    CustomTokenObtainPairView,
    ParentLoginView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterUserView,
)
from rest_framework_simplejwt.views import TokenRefreshView

from franchises.views import CentersListView, CitiesListView
from documents.pc_views import serve_pc_upload
from common.views import cms_public_media_file

# Function to create CSRF-exempt API include
def api_include(urlconf_module, namespace=None):
    """Include API URLs with CSRF exemption."""
    return path('api/', csrf_exempt(include(urlconf_module, namespace=namespace)))

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/", permanent=False), name="root"),
    path("admin/", admin.site.urls),
    # No-trailing-slash aliases (clients/proxies may omit `/` before POST bodies reach Django).
    path("api/auth/login", CustomTokenObtainPairView.as_view()),
    path("api/auth/login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/parent/login", ParentLoginView.as_view()),
    path("api/auth/parent/login/", ParentLoginView.as_view(), name="parent_login"),
    path("api/auth/crm/login", CrmLoginView.as_view()),
    path("api/auth/crm/login/", CrmLoginView.as_view(), name="crm_login"),
    path("api/auth/content-admin/login", ContentAdminLoginView.as_view()),
    path("api/auth/content-admin/login/", ContentAdminLoginView.as_view(), name="content_admin_login"),
    path("api/auth/password-reset", PasswordResetRequestView.as_view()),
    path("api/auth/password-reset/", PasswordResetRequestView.as_view(), name="password_reset_request"),
    path("api/auth/password-reset-confirm", PasswordResetConfirmView.as_view()),
    path("api/auth/password-reset-confirm/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("api/auth/register", RegisterUserView.as_view()),
    path("api/auth/register/", RegisterUserView.as_view(), name="register_user"),
    path("api/auth/check-parent-email", CheckParentEmailView.as_view()),
    path("api/auth/check-parent-email/", CheckParentEmailView.as_view(), name="check_parent_email"),
    path("api/auth/refresh", TokenRefreshView.as_view()),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/me", CurrentUserView.as_view()),
    path("api/auth/me/", CurrentUserView.as_view(), name="current_user"),
    path("api/cities", CitiesListView.as_view()),
    path("api/cities/", CitiesListView.as_view(), name="api-cities"),
    path("api/centers", CentersListView.as_view()),
    path("api/centers/", CentersListView.as_view(), name="api-centers"),
    path("api/accounts/", include("accounts.urls")),
    path("api/franchises/", include("franchises.urls")),
    path("api/events/", include("events.urls")),
    path("api/careers/", include("careers.urls")),
    path("api/enquiries/", include("enquiries.urls")),
    path("api/common/", include("common.urls")),
    path("api/updates/", include("updates.urls")),
    path("api/media/", include("gallery.urls")),
    path("api/students/", include("students.urls")),
    path("api/documents/", include("documents.urls")),
    path("api/plp/", include("plp_api.urls")),
    path("api/cms-files/<path:relative_path>", cms_public_media_file, name="cms-public-media-file"),
]

if settings.PC_DOCUMENTS_ROOT:
    urlpatterns += [
        re_path(
            r"^media/pc/(?P<relative_path>.+)$",
            serve_pc_upload,
            name="pc-documents",
        ),
    ]

# Serve static and media files in development
if settings.DEBUG:
    # Use staticfiles_urlpatterns() to serve static files from all installed apps
    # This includes Django admin static files
    urlpatterns += staticfiles_urlpatterns()
    # Serve media files
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # In production, static files should be served by the web server
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
