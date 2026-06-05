from django.db.models import Q
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminUser, IsFranchiseUser
from accounts.profile_access import franchise_profile_for_user
from .franchise_geo import (
    cities_from_franchises,
    filter_queryset_by_city,
    filter_queryset_by_search,
    filter_queryset_by_state,
    public_franchise_queryset,
    state_choices_from_franchises,
)
from .models import Franchise, ParentProfile, FranchiseLocation, FranchiseHeroSlide, FranchiseGalleryItem
from .serializers import (
    FranchiseCreateSerializer,
    FranchiseLocationSerializer,
    FranchiseProfileSerializer,
    FranchiseSerializer,
    FranchiseUpdateSerializer,
    ParentSerializer,
    PublicFranchiseSerializer,
    FranchiseHeroSlideSerializer,
    FranchiseGalleryItemSerializer,
    CityOptionSerializer,
    CentreOptionSerializer,
)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def state_choices_view(request):
    """Return states that have at least one centre (from ``franchise`` table)."""
    return Response(state_choices_from_franchises())


class FranchiseLocationViewSet(viewsets.ReadOnlyModelViewSet):
    """Public read-only endpoint for franchise locations."""
    serializer_class = FranchiseLocationSerializer
    permission_classes = [permissions.AllowAny]
    queryset = FranchiseLocation.objects.filter(is_active=True)


class AdminFranchiseLocationViewSet(viewsets.ModelViewSet):
    """Admin endpoint for managing franchise locations (CRUD)."""
    serializer_class = FranchiseLocationSerializer
    permission_classes = [IsAdminUser]
    queryset = FranchiseLocation.objects.all()
    
    def get_queryset(self):
        # Admin can see all locations including inactive ones
        return self.queryset.order_by('display_order', 'city_name')


class AdminFranchiseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    # Do not select_related(admin, user): INNER JOIN drops centres whose login user was removed.
    queryset = Franchise.objects.all()
    pagination_class = None  # Admin CMS lists every centre in one response

    def get_queryset(self):
        # Single-admin setup: return all franchises for the admin to view/edit/delete
        return self.queryset.order_by("city", "name")

    def get_serializer_class(self):
        if self.action == "create":
            return FranchiseCreateSerializer
        if self.action in ["update", "partial_update"]:
            return FranchiseUpdateSerializer
        return FranchiseSerializer

    def perform_create(self, serializer):
        serializer.save(admin=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

    def perform_destroy(self, instance):
        # Allow any admin to delete franchises
        instance.delete()


class FranchiseProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = FranchiseProfileSerializer
    permission_classes = [IsFranchiseUser]

    def get_object(self):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            raise PermissionDenied("Franchise profile not found")
        return franchise


class FranchiseParentViewSet(viewsets.ModelViewSet):
    serializer_class = ParentSerializer
    permission_classes = [IsFranchiseUser]
    pagination_class = None  # Centre parent list + search must see all rows (not first page of 20)
    queryset = ParentProfile.objects.select_related("user", "franchise")

    def get_queryset(self):
        from django.db.models import Q

        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return ParentProfile.objects.none()
        qs = self.queryset.filter(franchise=franchise)
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(
                Q(user__email__icontains=search)
                | Q(user__full_name__icontains=search)
                | Q(child_name__icontains=search)
                | Q(phone__icontains=search)
                | Q(notes__icontains=search)
                | Q(Emailid__icontains=search)
            )
        return qs.order_by("user__full_name", "id")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["franchise"] = franchise_profile_for_user(self.request.user)
        return context

    def list(self, request, *args, **kwargs):
        franchise = franchise_profile_for_user(request.user)
        if not franchise:
            return Response(
                {
                    "detail": (
                        "This login is not linked to a centre (franchise). "
                        "Use your centre login, or contact support to link the account."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().list(request, *args, **kwargs)

    def perform_destroy(self, instance):
        franchise = franchise_profile_for_user(self.request.user)
        if instance.franchise != franchise:
            raise PermissionDenied("Cannot delete parent outside your franchise")
        instance.user.delete()


class AdminParentListView(generics.ListAPIView):
    serializer_class = ParentSerializer
    permission_classes = [IsAdminUser]
    queryset = ParentProfile.objects.select_related("user", "franchise")

    def get_queryset(self):
        return self.queryset.filter(franchise__admin=self.request.user)


class PublicFranchiseDetailView(generics.RetrieveAPIView):
    serializer_class = PublicFranchiseSerializer
    lookup_field = "slug"
    permission_classes = [permissions.AllowAny]
    queryset = public_franchise_queryset().prefetch_related("events__media")


class PublicFranchiseListView(generics.ListAPIView):
    """Public view for listing all franchises with optional filtering."""
    serializer_class = PublicFranchiseSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None  # Locate a Centre / maps need the full filtered set

    def get_queryset(self):
        # Do not select_related(admin, user): INNER JOIN drops centres whose login rows were removed.
        queryset = public_franchise_queryset()

        state = (self.request.query_params.get("state") or "").strip() or None
        city = (self.request.query_params.get("city") or "").strip() or None
        search = (self.request.query_params.get("search") or "").strip() or None

        if state:
            queryset = filter_queryset_by_state(queryset, state)
        if city:
            queryset = filter_queryset_by_city(queryset, city)
        if search:
            queryset = filter_queryset_by_search(
                queryset,
                search,
                within_filters=bool(state or city),
            )

        return queryset.order_by("city", "name")


class PublicStatsView(generics.GenericAPIView):
    """Public marketing stats for the home page and related UI."""
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        return Response({
            'total_schools': public_franchise_queryset().count(),
            'total_cities': len(cities_from_franchises()),
            'total_students': 100000,
        })


class PublicLocationListView(generics.GenericAPIView):
    """Distinct cities + centre counts from the ``franchise`` table (not ``franchise_location``)."""
    permission_classes = [permissions.AllowAny]
    queryset = public_franchise_queryset()

    def get_queryset(self):
        return self.queryset

    def get(self, request, *args, **kwargs):
        return Response(cities_from_franchises())


class FranchiseHeroSlideViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing franchise hero slides.
    Allows Franchise Users to create, update, delete their own slides.
    Also provides a public endpoint for reading slides if needed (or handle via permissions).
    Here we focus on the Dashboard management part.
    """
    serializer_class = FranchiseHeroSlideSerializer
    permission_classes = [IsFranchiseUser] # Only logged-in franchise users can manage

    def get_queryset(self):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return FranchiseHeroSlide.objects.none()
        return FranchiseHeroSlide.objects.filter(franchise=franchise)

    def perform_create(self, serializer):
        import logging

        logger = logging.getLogger(__name__)
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            logger.error(
                "User %s (role: %s) has no franchise_profile",
                getattr(self.request.user, "email", ""),
                getattr(self.request.user, "role", ""),
            )
            raise PermissionDenied(
                "You must be a franchise user with a valid franchise profile to create a slide."
            )
        logger.info("Creating hero slide for franchise: %s", franchise.name)
        serializer.save(franchise=franchise)


class PublicFranchiseHeroSlideResultSet(viewsets.ReadOnlyModelViewSet):
    """
    Public ViewSet to fetch slides for a specific franchise (by slug or ID).
    Used by the Login Page or Public Page.
    """
    serializer_class = FranchiseHeroSlideSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        # We expect a query param 'franchise_slug' or similar
        slug = self.request.query_params.get('franchise_slug')
        if slug:
            return FranchiseHeroSlide.objects.filter(franchise__slug=slug, is_active=True).order_by('order', '-created_at')
        return FranchiseHeroSlide.objects.none()


class FranchiseGalleryItemViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing franchise gallery items (photos/videos).
    Allows Franchise Users to create, update, delete their own gallery items.
    """
    serializer_class = FranchiseGalleryItemSerializer
    permission_classes = [IsFranchiseUser]

    def get_queryset(self):
        # Return items only for the logged-in user's franchise
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            return FranchiseGalleryItem.objects.none()
        return FranchiseGalleryItem.objects.filter(franchise=franchise)

    def perform_create(self, serializer):
        franchise = franchise_profile_for_user(self.request.user)
        if not franchise:
            raise PermissionDenied("You must be a franchise user to create a gallery item.")
        serializer.save(franchise=franchise)


def _distinct_franchise_cities():
    """Non-empty distinct ``city`` values from franchise rows."""
    return (
        Franchise.objects.all()
        .exclude(Q(city__isnull=True) | Q(city__exact=""))
        .values_list("city", flat=True)
        .distinct()
        .order_by("city")
    )


class CitiesListView(APIView):
    """
    GET /api/cities/

    Returns distinct ``franchise.city`` values for the first form dropdown.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        raw = _distinct_franchise_cities()
        names = sorted({str(s).strip() for s in raw if s and str(s).strip()}, key=str.casefold)
        results = CityOptionSerializer([{"name": n} for n in names], many=True).data
        return Response({"count": len(results), "results": results})


class CentersListView(APIView):
    """
    GET /api/centers/?city=Chennai

    Query param ``city`` filters ``franchise.city`` (case-insensitive).
    Returns centres' ``name`` values for location dropdowns.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        city = (request.query_params.get("city") or "").strip()
        if not city:
            raise ValidationError({"city": "Query parameter 'city' is required."})
        if len(city) > 255:
            raise ValidationError({"city": "Value is too long."})

        queryset = filter_queryset_by_city(
            Franchise.objects.all(),
            city,
        ).exclude(Q(name__isnull=True) | Q(name__exact="")).order_by("name")
        results = CentreOptionSerializer(queryset, many=True).data
        return Response({"count": len(results), "city": city, "results": results})
