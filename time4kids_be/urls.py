from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path, re_path
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import RedirectView

from accounts.views import CurrentUserView, CustomTokenObtainPairView, ParentLoginView
from rest_framework_simplejwt.views import TokenRefreshView

# Function to create CSRF-exempt API include
def api_include(urlconf_module, namespace=None):
    """Include API URLs with CSRF exemption."""
    return path('api/', csrf_exempt(include(urlconf_module, namespace=namespace)))

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/", permanent=False), name="root"),
    path("admin/", admin.site.urls),
    path("api/auth/login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/parent/login/", ParentLoginView.as_view(), name="parent_login"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/me/", CurrentUserView.as_view(), name="current_user"),
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
