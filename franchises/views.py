from django.db.models import Count, Q
from rest_framework import generics, permissions, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from accounts.permissions import IsAdminUser, IsFranchiseUser
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
)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def state_choices_view(request):
    """Return list of Indian states with codes and names."""
    states = [
        {'code': code, 'name': name}
        for code, name in FranchiseLocation.STATE_CHOICES
    ]
    return Response(states)


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
    queryset = Franchise.objects.select_related("admin", "user")

    def get_queryset(self):
        # Single-admin setup: return all franchises for the admin to view/edit/delete
        return self.queryset

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
        franchise = getattr(self.request.user, "franchise_profile", None)
        if not franchise:
            raise PermissionDenied("Franchise profile not found")
        return franchise


class FranchiseParentViewSet(viewsets.ModelViewSet):
    serializer_class = ParentSerializer
    permission_classes = [IsFranchiseUser]
    queryset = ParentProfile.objects.select_related("user", "franchise")

    def get_queryset(self):
        franchise = getattr(self.request.user, "franchise_profile", None)
        if not franchise:
            return ParentProfile.objects.none()
        return self.queryset.filter(franchise=franchise)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["franchise"] = getattr(self.request.user, "franchise_profile", None)
        return context

    def perform_destroy(self, instance):
        franchise = getattr(self.request.user, "franchise_profile", None)
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
    queryset = Franchise.objects.filter(is_active=True).prefetch_related("events__media")


class PublicFranchiseListView(generics.ListAPIView):
    """Public view for listing all active franchises with optional filtering."""
    serializer_class = PublicFranchiseSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = Franchise.objects.filter(is_active=True).select_related(
            "admin", "user"
        )
        
        # Filter by state
        state = self.request.query_params.get('state', None)
        if state:
            # Handle both code (e.g., "AP") and full name matches
            state_dict = dict(FranchiseLocation.STATE_CHOICES)
            state_full_name = state_dict.get(state.upper(), state)
            
            queryset = queryset.filter(
                Q(state__iexact=state) | 
                Q(state__icontains=state_full_name) |
                Q(state__icontains=state)
            )
        
        # Filter by city
        city = self.request.query_params.get('city', None)
        if city:
            queryset = queryset.filter(city__iexact=city)
        
        # Search across name, city, and address with weighted relevance
        search = self.request.query_params.get('search', None)
        if search:
            from django.db.models import Case, When, Value, IntegerField
            
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(city__icontains=search) |
                Q(address__icontains=search)
            ).annotate(
                relevance=Case(
                    # Exact name match: highest priority
                    When(name__iexact=search, then=Value(4)),
                    # Name contains search: high priority
                    When(name__icontains=search, then=Value(3)),
                    # City contains search: medium priority
                    When(city__icontains=search, then=Value(2)),
                    # Address contains search: lower priority
                    When(address__icontains=search, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField()
                )
            ).order_by('-relevance', 'city', 'name')
            return queryset
        
        return queryset.order_by('city', 'name')


class PublicStatsView(generics.GenericAPIView):
    """Return dynamic stats for the home page with realistic baselines."""
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        # Calculate real database counts
        real_schools = Franchise.objects.filter(is_active=True).count()
        real_cities = FranchiseLocation.objects.filter(is_active=True).count() # Changed to count of active Locations
        real_students = ParentProfile.objects.count()

        # Business logic: Use real counts for schools and cities to match other views.
        # Keep baseline for students as requested.
        
        baseline_students = 50000

        return Response({
            'total_schools': real_schools,
            'total_cities': real_cities,
            'total_students': baseline_students + real_students
        })


class PublicLocationListView(generics.GenericAPIView):
    """Return all active locations with their franchise counts."""
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        # Get all active locations
        active_locations = FranchiseLocation.objects.filter(is_active=True).order_by('display_order', 'city_name')
        
        # Get franchise counts per city (case-insensitive grouping would be better but city is CharField)
        # We'll do a simple count for now.
        franchise_counts = Franchise.objects.filter(is_active=True).values('city').annotate(count=Count('id'))
        count_map = {item['city'].lower(): item['count'] for item in franchise_counts}
        
        locations = []
        for loc in active_locations:
            locations.append({
                'id': loc.id,
                'city_name': loc.city_name,
                'city': loc.city_name, # Alias for frontend compatibility
                'state': loc.state,
                'state_display': loc.get_state_display(),
                'landmark_name': loc.landmark_name or 'City Center',
                'landmark_type': loc.landmark_type,
                'is_active': loc.is_active,
                'display_order': loc.display_order,
                'franchise_count': count_map.get(loc.city_name.lower(), 0)
            })
        
        return Response(locations)


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
        # Return slides only for the logged-in user's franchise
        if not hasattr(self.request.user, "franchise_profile"):
            return FranchiseHeroSlide.objects.none()
        return FranchiseHeroSlide.objects.filter(franchise=self.request.user.franchise_profile)

    def perform_create(self, serializer):
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            if not hasattr(self.request.user, "franchise_profile"):
                logger.error(f"User {self.request.user.email} (role: {self.request.user.role}) has no franchise_profile")
                raise PermissionDenied("You must be a franchise user with a valid franchise profile to create a slide.")
            
            franchise = self.request.user.franchise_profile
            logger.info(f"Creating hero slide for franchise: {franchise.name}")
            serializer.save(franchise=franchise)
        except Exception as e:
            logger.exception(f"Error creating hero slide: {str(e)}")
            raise


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
        franchise = getattr(self.request.user, "franchise_profile", None)
        if not franchise:
            return FranchiseGalleryItem.objects.none()
        return FranchiseGalleryItem.objects.filter(franchise=franchise)

    def perform_create(self, serializer):
        franchise = getattr(self.request.user, "franchise_profile", None)
        if not franchise:
            raise PermissionDenied("You must be a franchise user to create a gallery item.")
        serializer.save(franchise=franchise)
