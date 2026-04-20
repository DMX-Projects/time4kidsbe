from django.db.models import Q
from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from accounts.permissions import IsFranchiseUser, IsParentUser, IsAdminOrApproverUser
from accounts.profile_access import franchise_profile_for_user, parent_profile_for_user
from .models import ParentDocument, DocumentCategory, FranchiseDocument, FranchiseDocumentCategory, IndentRequest
from .serializers import ParentDocumentSerializer, FranchiseDocumentSerializer, IndentRequestSerializer


class ParentDocumentListView(generics.ListAPIView):
    """List all documents accessible to parent (franchise-specific + global) including holiday lists"""
    serializer_class = ParentDocumentSerializer
    permission_classes = [IsParentUser]
    pagination_class = None  # Disable pagination to show all documents

    def get_queryset(self):
        parent_profile = parent_profile_for_user(self.request.user)
        
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
    parent_profile = parent_profile_for_user(request.user)
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


@api_view(["GET"])
@permission_classes([IsFranchiseUser])
def franchise_documents_by_category(request, category: str):
    """
    Get franchise resource hub documents filtered by category.
    Returns franchise-specific documents and also global documents (franchise is null).
    """
    franchise_profile = franchise_profile_for_user(request.user)
    if not franchise_profile:
        return Response({"error": "Franchise profile not found"}, status=403)

    franchise = franchise_profile

    valid_categories = [choice[0] for choice in FranchiseDocumentCategory.choices]
    if category not in valid_categories:
        return Response({"error": "Invalid category"}, status=400)

    documents = FranchiseDocument.objects.filter(
        category=category,
        is_active=True,
    ).filter(
        Q(franchise=franchise) | Q(franchise__isnull=True)
    ).order_by("order", "-created_at")

    serializer = FranchiseDocumentSerializer(documents, many=True)
    return Response(serializer.data)


class FranchiseParentDocumentListCreateView(generics.ListCreateAPIView):
    """Franchise can upload/manage parent-facing documents for their own centre."""

    serializer_class = ParentDocumentSerializer
    permission_classes = [IsFranchiseUser]
    pagination_class = None

    def get_queryset(self):
        franchise_profile = franchise_profile_for_user(self.request.user)
        if not franchise_profile:
            return ParentDocument.objects.none()
        return ParentDocument.objects.filter(franchise=franchise_profile).order_by("category", "order", "-created_at")

    def perform_create(self, serializer):
        franchise_profile = franchise_profile_for_user(self.request.user)
        if not franchise_profile:
            raise PermissionDenied("Franchise profile not found")
        serializer.save(franchise=franchise_profile)


class FranchiseParentDocumentDeleteView(generics.DestroyAPIView):
    """Franchise can delete only their own parent-facing documents."""

    serializer_class = ParentDocumentSerializer
    permission_classes = [IsFranchiseUser]

    def get_queryset(self):
        franchise_profile = franchise_profile_for_user(self.request.user)
        if not franchise_profile:
            return ParentDocument.objects.none()
        return ParentDocument.objects.filter(franchise=franchise_profile)


class FranchiseIndentRequestListCreateView(generics.ListCreateAPIView):
    """Create and list indent requests for the logged-in franchise user."""

    serializer_class = IndentRequestSerializer
    permission_classes = [IsFranchiseUser]

    def get_queryset(self):
        franchise_profile = franchise_profile_for_user(self.request.user)
        if not franchise_profile:
            return IndentRequest.objects.none()
        return IndentRequest.objects.filter(franchise=franchise_profile)

    def perform_create(self, serializer):
        franchise_profile = franchise_profile_for_user(self.request.user)
        if not franchise_profile:
            raise PermissionDenied("Franchise profile not found")
        serializer.save(franchise=franchise_profile)


class AdminIndentRequestListView(generics.ListAPIView):
    """Admin can view indent requests from all franchises."""

    serializer_class = IndentRequestSerializer
    permission_classes = [IsAdminOrApproverUser]

    def get_queryset(self):
        return IndentRequest.objects.all().order_by("-requested_at")


class AdminIndentRequestUpdateView(generics.UpdateAPIView):
    """Admin can approve/reject an indent request."""

    serializer_class = IndentRequestSerializer
    permission_classes = [IsAdminOrApproverUser]
    queryset = IndentRequest.objects.all().order_by("-requested_at")

