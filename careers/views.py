from rest_framework import generics, permissions, viewsets

from accounts.permissions import IsAdminUser
from .models import Career
from .serializers import CareerSerializer


class AdminCareerViewSet(viewsets.ModelViewSet):
    serializer_class = CareerSerializer
    permission_classes = [IsAdminUser]
    queryset = Career.objects.all()

    def get_queryset(self):
        return self.queryset.filter(admin=self.request.user)

    def perform_create(self, serializer):
        serializer.save(admin=self.request.user)


class PublicCareerListView(generics.ListAPIView):
    serializer_class = CareerSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Career.objects.filter(is_active=True)
