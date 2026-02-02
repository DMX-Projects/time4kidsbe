from django.db.models import Q
from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from accounts.permissions import IsParentUser
from .models import ParentDocument, DocumentCategory
from .serializers import ParentDocumentSerializer


class ParentDocumentListView(generics.ListAPIView):
    """List all documents accessible to parent (franchise-specific + global) including holiday lists"""
    serializer_class = ParentDocumentSerializer
    permission_classes = [IsParentUser]
    pagination_class = None  # Disable pagination to show all documents

    def get_queryset(self):
        parent_profile = getattr(self.request.user, "parent_profile", None)
        
        # If parent has a profile, show franchise-specific + global documents
        # If no profile, show only global documents
        if parent_profile and parent_profile.franchise:
            franchise = parent_profile.franchise
            return ParentDocument.objects.filter(
                is_active=True
            ).filter(
                Q(franchise=franchise) | Q(franchise__isnull=True)
            ).select_related('franchise').order_by('category', 'order', '-created_at')
        else:
            # Return only global documents if no parent profile
            return ParentDocument.objects.filter(
                is_active=True,
                franchise__isnull=True
            ).select_related('franchise').order_by('category', 'order', '-created_at')


@api_view(['GET'])
@permission_classes([IsParentUser])
def parent_documents_by_category(request, category):
    """Get documents filtered by category"""
    parent_profile = getattr(request.user, "parent_profile", None)
    if not parent_profile:
        return Response({"error": "Parent profile not found"}, status=404)
    
    franchise = parent_profile.franchise
    
    # Validate category (including HOLIDAY_LISTS)
    valid_categories = [choice[0] for choice in DocumentCategory.choices]
    if category not in valid_categories:
        return Response({"error": "Invalid category"}, status=400)
    
    documents = ParentDocument.objects.filter(
        category=category,
        is_active=True
    ).filter(
        Q(franchise=franchise) | Q(franchise__isnull=True)
    ).order_by('order', '-created_at')
    
    serializer = ParentDocumentSerializer(documents, many=True)
    return Response(serializer.data)

