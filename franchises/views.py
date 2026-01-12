from django.db.models import Count, Q
from rest_framework import generics, permissions, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from accounts.permissions import IsAdminUser, IsFranchiseUser
from .models import Franchise, ParentProfile, FranchiseLocation
from .serializers import (
    FranchiseCreateSerializer,
    FranchiseLocationSerializer,
    FranchiseProfileSerializer,
    FranchiseSerializer,
    FranchiseUpdateSerializer,
    ParentSerializer,
    PublicFranchiseSerializer,
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


class PublicLocationListView(generics.GenericAPIView):
    """Return unique cities from active franchises for city ladder display."""
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        # Get unique city-state combinations from active franchises
        franchises = Franchise.objects.filter(is_active=True).values('city', 'state').distinct()
        
        # Format as list with display_order based on alphabetical order
        locations = []
        for idx, franchise in enumerate(franchises.order_by('state', 'city')):
            # Find a representative franchise for this city to get additional info
            # Also try to find a matching FranchiseLocation to get landmark info
            franchise_location = FranchiseLocation.objects.filter(
                city_name__iexact=franchise['city']
            ).first()
            
            locations.append({
                'id': idx + 1,
                'city_name': franchise['city'],
                'state': franchise['state'],
                'state_display': dict(FranchiseLocation.STATE_CHOICES).get(franchise['state'], franchise['state']),
                'landmark_name': franchise_location.landmark_name if franchise_location else 'City Center',
                'landmark_type': franchise_location.landmark_type if franchise_location else 'fort_generic',
                'is_active': True,
                'display_order': idx
            })
        
        return Response(locations)
        
        return Response(locations)
