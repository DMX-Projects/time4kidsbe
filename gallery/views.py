from rest_framework import viewsets
from .models import MediaItem
from .serializers import MediaItemSerializer
from rest_framework.permissions import IsAuthenticatedOrReadOnly

class MediaItemViewSet(viewsets.ModelViewSet):
    queryset = MediaItem.objects.all()
    serializer_class = MediaItemSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
