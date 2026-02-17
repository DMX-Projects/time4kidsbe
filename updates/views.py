from rest_framework import viewsets
from .models import Update
from .serializers import UpdateSerializer
from rest_framework.permissions import AllowAny, IsAuthenticated

class UpdateViewSet(viewsets.ModelViewSet):
    queryset = Update.objects.all()
    serializer_class = UpdateSerializer
    permission_classes = [AllowAny] # Ideally should be IsAuthenticated for write, AllowAny for read

    def get_queryset(self):
        queryset = Update.objects.all().order_by('-start_date')
        
        # Filter by franchise slug (for public school page)
        franchise_slug = self.request.query_params.get('franchise_slug')
        if franchise_slug:
            queryset = queryset.filter(franchise__slug=franchise_slug, is_active=True)
            return queryset

        # Filter by logged-in user's franchise (for dashboard)
        user = self.request.user
        if user.is_authenticated and hasattr(user, 'franchise_profile'):
             return queryset.filter(franchise=user.franchise_profile)
        
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_authenticated and hasattr(user, 'franchise_profile'):
            serializer.save(franchise=user.franchise_profile)
        else:
             # Fallback for testing/admin if needed, or raise error
             serializer.save()
