from rest_framework import viewsets
from .models import MediaItem
from .serializers import MediaItemSerializer
from rest_framework.permissions import IsAuthenticatedOrReadOnly

class MediaItemViewSet(viewsets.ModelViewSet):
    queryset = MediaItem.objects.all()
    serializer_class = MediaItemSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = MediaItem.objects.all()
        category = self.request.query_params.get('category', None)
        if category is not None:
            queryset = queryset.filter(category=category)
        return queryset
