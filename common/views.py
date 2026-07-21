import copy
import mimetypes
import os

from django.conf import settings
from django.http import FileResponse, Http404
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET
from rest_framework import viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError

from accounts.models import User, UserRole
from accounts.permissions import IsAdminUser
from .models import HeroSlide, HomeTestimonial, HomePageContent, MarketingAsset, StudentsKitPage, State, City
from .serializers import (
    HeroSlideSerializer,
    HomeTestimonialSerializer,
    MarketingAssetSerializer,
    StudentsKitPageSerializer,
)
from .students_kit_sync import sync_students_kit_franchise_document
from .home_page_defaults import DEFAULT_HOME_PAGE_DATA, normalize_home_page_data


class HeroSlideViewSet(viewsets.ModelViewSet):
    serializer_class = HeroSlideSerializer
    pagination_class = None

    def get_queryset(self):
        qs = HeroSlide.objects.all().order_by("order", "id")
        if self.action in ("list", "retrieve"):
            user = self.request.user
            if user.is_authenticated and isinstance(user, User) and user.normalized_role() == UserRole.ADMIN.value:
                return qs
            return qs.filter(is_active=True)
        return qs

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAdminUser()]


class HomeTestimonialViewSet(viewsets.ModelViewSet):
    """Public list: active quotes only. Admin: full CRUD."""

    serializer_class = HomeTestimonialSerializer
    pagination_class = None

    def get_queryset(self):
        qs = HomeTestimonial.objects.all().order_by("order", "id")
        if self.action in ("list", "retrieve"):
            user = self.request.user
            if user.is_authenticated and isinstance(user, User) and user.normalized_role() == UserRole.ADMIN.value:
                return qs
            return qs.filter(is_active=True)
        return qs

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAdminUser()]


class StudentsKitPageViewSet(viewsets.ModelViewSet):
    """Public: active kit posters. Admin: upload image + PDF for each programme."""

    serializer_class = StudentsKitPageSerializer
    pagination_class = None
    lookup_field = "slug"
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "put", "patch", "head", "options"]

    def get_queryset(self):
        qs = StudentsKitPage.objects.all().order_by("order", "slug")
        if self.action in ("list", "retrieve"):
            user = self.request.user
            if user.is_authenticated and isinstance(user, User) and user.normalized_role() == UserRole.ADMIN.value:
                return qs
            return qs.filter(is_active=True)
        return qs

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAdminUser()]

    def perform_update(self, serializer):
        instance = serializer.save()
        sync_students_kit_franchise_document(instance)


class MarketingAssetViewSet(viewsets.ModelViewSet):
    """Public list: active assets only. Admin: full CRUD."""

    serializer_class = MarketingAssetSerializer
    pagination_class = None
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = MarketingAsset.objects.all().order_by("-updated_at")
        if self.action in ("list", "retrieve"):
            user = self.request.user
            if user.is_authenticated and isinstance(user, User) and user.normalized_role() == UserRole.ADMIN.value:
                return qs
            return qs.filter(is_active=True)
        return qs

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAdminUser()]


class HomePageContentView(APIView):
    """GET: public JSON for homepage marketing sections. PUT: admin replaces entire document."""

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        obj, _ = HomePageContent.objects.get_or_create(
            pk=1,
            defaults={"data": copy.deepcopy(DEFAULT_HOME_PAGE_DATA)},
        )
        data = obj.data
        if not isinstance(data, dict):
            data = copy.deepcopy(DEFAULT_HOME_PAGE_DATA)
            obj.data = data
            obj.save(update_fields=["data", "updated_at"])
        elif not data:
            data = copy.deepcopy(DEFAULT_HOME_PAGE_DATA)
            obj.data = data
            obj.save(update_fields=["data", "updated_at"])
        try:
            payload = normalize_home_page_data(data)
        except Exception:
            payload = copy.deepcopy(DEFAULT_HOME_PAGE_DATA)
        return Response(payload)

    def put(self, request):
        body = request.data
        if not isinstance(body, dict):
            raise ValidationError({"detail": "Body must be a JSON object."})
        obj, _ = HomePageContent.objects.get_or_create(
            pk=1,
            defaults={"data": copy.deepcopy(DEFAULT_HOME_PAGE_DATA)},
        )
        obj.data = normalize_home_page_data(copy.deepcopy(body))
        obj.save(update_fields=["data", "updated_at"])
        try:
            return Response(normalize_home_page_data(obj.data))
        except Exception:
            return Response(copy.deepcopy(DEFAULT_HOME_PAGE_DATA))


class HomePageContentResetView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        obj, _ = HomePageContent.objects.update_or_create(
            pk=1,
            defaults={"data": copy.deepcopy(DEFAULT_HOME_PAGE_DATA)},
        )
        try:
            return Response(normalize_home_page_data(obj.data))
        except Exception:
            return Response(copy.deepcopy(DEFAULT_HOME_PAGE_DATA))


class PageContentView(APIView):
    """
    GET: public JSON for a specific page's marketing sections (slug-based).
    PUT: admin replaces entire document for that page.
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdminUser()]

    def get_default_data(self, slug):
        from .home_page_defaults import (
            ADMISSION_PAGE_DATA,
            FRANCHISE_PAGE_DATA,
            PROGRAMS_PAGE_DATA,
            FAQ_PAGE_DATA,
            ABOUT_PAGE_DATA,
            CENTRE_PROGRAM_CARDS_DATA,
        )
        from .footer_defaults import FOOTER_PAGE_DATA
        if slug == "admission":
            return ADMISSION_PAGE_DATA
        if slug == "franchise-opportunity":
            return FRANCHISE_PAGE_DATA
        if slug == "programs":
            return PROGRAMS_PAGE_DATA
        if slug == "faq":
            return FAQ_PAGE_DATA
        if slug == "about":
            return ABOUT_PAGE_DATA
        if slug == "footer":
            return FOOTER_PAGE_DATA
        if slug == "centre-program-cards":
            return CENTRE_PROGRAM_CARDS_DATA
        if slug == "centre-page-nav-custom":
            return {"customTopSections": [], "staticExtensions": []}
        if slug == "parent-app-nav-custom":
            return {"customTopSections": [], "staticExtensions": []}
        return {}

    def get(self, request, slug):
        from .models import PageContent
        from .home_page_defaults import normalize_admission_page_data

        obj, _ = PageContent.objects.get_or_create(
            slug=slug,
            defaults={"data": copy.deepcopy(self.get_default_data(slug))},
        )
        data = obj.data
        if slug == "admission":
            data = normalize_admission_page_data(data)
        if slug == "franchise-opportunity" and isinstance(data, dict):
            testimonials = data.get("testimonials")
            if isinstance(testimonials, list):
                for item in testimonials:
                    if isinstance(item, dict):
                        item["location"] = ""
            main_branch = data.get("main_branch")
            if isinstance(main_branch, dict):
                if (
                    main_branch.get("heading_prefix") == "Visit Our"
                    and main_branch.get("heading_accent") == "Main Branch"
                ):
                    main_branch["heading_prefix"] = "Connect with Our"
                    main_branch["heading_accent"] = "Representative"
                address_html = main_branch.get("address_html") or ""
                if "Triumphant Institute of Management Education" in address_html:
                    main_branch["address_html"] = (
                        "Kids Early Education Pvt. Ltd.<br />95B, Second Floor<br />"
                        "Siddamsetty Complex<br />Parklane, Secunderabad<br />500003"
                    )
                if main_branch.get("email") == "info@timekidspreschools.com":
                    main_branch["email"] = "admissions@timekidspreschools.com"
                if not (main_branch.get("regional_office_title") or "").strip():
                    main_branch["regional_office_title"] = "T.I.M.E. Kids Regional Offices"
                from .home_page_defaults import (
                    REGIONAL_OFFICES_ADDRESS_HTML,
                    _should_migrate_regional_address,
                )

                regional_addr = main_branch.get("regional_address_html") or ""
                if (
                    _should_migrate_regional_address(regional_addr)
                    or regional_addr.strip() == (main_branch.get("address_html") or "").strip()
                ):
                    main_branch["regional_address_html"] = REGIONAL_OFFICES_ADDRESS_HTML
        return Response(data)

    def put(self, request, slug):
        from .models import PageContent
        body = request.data
        if not isinstance(body, dict):
            raise ValidationError({"detail": "Body must be a JSON object."})
        obj, _ = PageContent.objects.get_or_create(
            slug=slug,
            defaults={"data": copy.deepcopy(self.get_default_data(slug))},
        )
        obj.data = body
        obj.save(update_fields=["data", "updated_at"])
        return Response(obj.data)


# States shown on franchise landing-page enquiry forms.
FRANCHISE_LP_STATES = (
    "Tamil Nadu",
    "Kerala",
    "Karnataka",
    "Andhra Pradesh",
    "Telangana",
    "Maharashtra",
)

# Cities excluded from specific states on franchise LPs.
FRANCHISE_LP_EXCLUDED_CITIES = {
    "Maharashtra": {"mumbai"},
}


class StatesListView(APIView):
    """GET /api/common/states/?scope=franchise-lp — public list from ``common_state``."""

    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        qs = State.objects.all().order_by("name")
        scope = (request.query_params.get("scope") or "").strip().lower()
        if scope == "franchise-lp":
            by_name = {s.name.casefold(): s for s in qs.filter(name__in=FRANCHISE_LP_STATES)}
            ordered = []
            for name in FRANCHISE_LP_STATES:
                state = by_name.get(name.casefold())
                if state:
                    ordered.append(state)
            results = [{"id": s.id, "name": s.name} for s in ordered]
            return Response({"count": len(results), "results": results})

        results = [{"id": s.id, "name": s.name} for s in qs]
        return Response({"count": len(results), "results": results})


class CitiesByStateView(APIView):
    """
    GET /api/common/cities/?state=Assam&scope=franchise-lp

    Public list from ``common_city`` filtered by state name (case-insensitive).
    """

    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        state_name = (request.query_params.get("state") or "").strip()
        if not state_name:
            raise ValidationError({"state": "Query parameter 'state' is required."})

        scope = (request.query_params.get("scope") or "").strip().lower()
        if scope == "franchise-lp":
            allowed = {name.casefold() for name in FRANCHISE_LP_STATES}
            if state_name.casefold() not in allowed:
                return Response({"count": 0, "state": state_name, "results": []})

        state = State.objects.filter(name__iexact=state_name).first()
        if not state:
            return Response({"count": 0, "state": state_name, "results": []})

        qs = City.objects.filter(state=state).order_by("name")
        excluded = {
            name.casefold()
            for name in FRANCHISE_LP_EXCLUDED_CITIES.get(state.name, set())
        } if scope == "franchise-lp" else set()

        results = []
        for c in qs:
            if excluded and c.name.strip().casefold() in excluded:
                continue
            results.append({"id": c.id, "name": c.name})

        return Response({"count": len(results), "state": state.name, "results": results})


@require_GET
@cache_control(public=True, max_age=86400)
def cms_public_media_file(request, relative_path: str):
    """
    Public CMS uploads (hero slider, homepage blobs, gallery files) via /api/cms-files/…
    Use when nginx does not expose /media/ on the marketing domain.
    """
    rel = (relative_path or "").strip().lstrip("/")
    if not rel or ".." in rel.split("/"):
        raise Http404("Invalid path")

    media_root = os.path.realpath(str(settings.MEDIA_ROOT))
    full = os.path.realpath(os.path.join(media_root, rel))
    if full != media_root and not full.startswith(media_root + os.sep):
        raise Http404("Invalid path")
    if not os.path.isfile(full):
        raise Http404("File not found")

    content_type, _encoding = mimetypes.guess_type(full)
    if not content_type:
        content_type = "application/octet-stream"
    try:
        handle = open(full, "rb")
    except OSError:
        raise Http404("File not readable") from None
    return FileResponse(handle, content_type=content_type, filename=os.path.basename(full))
