import copy

from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError

from accounts.models import User, UserRole
from accounts.permissions import IsAdminUser
from .models import HeroSlide, HomeTestimonial, HomePageContent, MarketingAsset
from .serializers import HeroSlideSerializer, HomeTestimonialSerializer, MarketingAssetSerializer
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


class MarketingAssetViewSet(viewsets.ModelViewSet):
    """Public list: active assets only. Admin: full CRUD."""
    serializer_class = MarketingAssetSerializer
    pagination_class = None

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
        from .home_page_defaults import ADMISSION_PAGE_DATA, FRANCHISE_PAGE_DATA, PROGRAMS_PAGE_DATA, FAQ_PAGE_DATA, ABOUT_PAGE_DATA
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
