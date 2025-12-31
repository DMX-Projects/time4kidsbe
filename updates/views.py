from rest_framework import viewsets
from .models import Update
from .serializers import UpdateSerializer

from rest_framework.permissions import AllowAny

class UpdateViewSet(viewsets.ModelViewSet):
    queryset = Update.objects.all().order_by('-date')
    serializer_class = UpdateSerializer
    permission_classes = [AllowAny]
