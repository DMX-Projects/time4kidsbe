from rest_framework import viewsets
from .models import HeroSlide
from .serializers import HeroSlideSerializer

class HeroSlideViewSet(viewsets.ModelViewSet):

    queryset = HeroSlide.objects.filter(is_active=True)
    serializer_class = HeroSlideSerializer
    permission_classes = [] 
    pagination_class = None # Show all slides at once
