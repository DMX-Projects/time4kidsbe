from pathlib import Path
import mimetypes

from django.conf import settings
from django.core.management import call_command
from django.db.models import Q, Count
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from accounts.models import UserRole
from accounts.permissions import IsFranchiseUser, IsParentUser, IsAdminOrApproverUser
from accounts.profile_access import franchise_profile_for_user, parent_profile_for_user
from .auth import QueryJWTAuthentication
from .download_names import (
    franchise_document_download_filename,
    parent_document_download_filename,
    safe_disposition_filename,
)
from .models import ParentDocument, DocumentCategory, FranchiseDocument, FranchiseDocumentCategory, IndentRequest
from .serializers import (
    ParentDocumentSerializer,
    AdminParentDocumentSerializer,
    FranchiseParentDocumentWriteSerializer,
    FranchiseDocumentSerializer,
    FranchiseCentreDocumentCreateSerializer,
    AdminFranchiseDocumentSerializer,
    IndentRequestSerializer,
)


class ParentDocumentListView(generics.ListAPIView):
    """List all active parent documents for parent app."""
    serializer_class = ParentDocumentSerializer
    permission_classes = [IsParentUser]
    pagination_class = None  # Disable pagination to show all documents

    def get_queryset(self):
        return _parent_documents_visible_queryset(self.request.user)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["merge_holiday_for_parent"] = True
        return ctx


@api_view(['GET'])
@permission_classes([IsParentUser])
def parent_documents_by_category(request, category):
    """Get active documents filtered by category"""

    # Validate category (including HOLIDAY_LISTS)
    valid_categories = [choice[0] for choice in DocumentCategory.choices]
    if category not in valid_categories:
        return Response({"error": "Invalid category"}, status=400)

    documents = _parent_documents_visible_queryset(request.user).filter(category=category)

    serializer = ParentDocumentSerializer(
        documents,
        many=True,
        context={"request": request, "merge_holiday_for_parent": True},
    )
    return Response(serializer.data)


def _norm_user_role(user) -> str:
    return str(getattr(user, "role", "") or "").strip().upper()


def _parent_documents_visible_queryset(user):
    """Active parent-app documents: global + parent's centre (when linked)."""
    from .parent_document_media import filter_parent_documents_by_media_type
    from .state_utils import franchise_state_code

    qs = ParentDocument.objects.filter(is_active=True).select_related("franchise")
    role = _norm_user_role(user)
    if role == UserRole.PARENT.value:
        profile = parent_profile_for_user(user)
        if profile and profile.franchise_id:
            qs = qs.filter(Q(franchise__isnull=True) | Q(franchise_id=profile.franchise_id))
            qs = _apply_holiday_centre_overrides(qs, profile.franchise_id)
            
            # Restrict global holiday lists to the parent's franchise state
            eff_state = franchise_state_code(profile.franchise)
            if eff_state:
                qs = qs.exclude(
                    Q(category=DocumentCategory.HOLIDAY_LISTS) &
                    Q(franchise__isnull=True) &
                    ~Q(state=eff_state)
                )
            else:
                # If centre has no valid state, hide all global holiday lists
                qs = qs.exclude(
                    Q(category=DocumentCategory.HOLIDAY_LISTS) &
                    Q(franchise__isnull=True)
                )
        else:
            qs = qs.filter(franchise__isnull=True)
            # Unlinked parents cannot see any state-specific global holiday lists
            qs = qs.exclude(category=DocumentCategory.HOLIDAY_LISTS)
            
    qs = filter_parent_documents_by_media_type(qs)
    return qs.order_by("category", "order", "-created_at")


def _apply_holiday_centre_overrides(qs, franchise_id):
    """
    Parents see centre holiday PDF instead of head-office global for the same state + year.
    Centre rows with manual entries only (no PDF) must not hide the head-office PDF.
    """
    from .state_utils import effective_holiday_academic_year, effective_holiday_state

    centre_holidays = (
        ParentDocument.objects.filter(
            is_active=True,
            category=DocumentCategory.HOLIDAY_LISTS,
            franchise_id=franchise_id,
        )
        .exclude(file="")
        .exclude(file__isnull=True)
        .select_related("franchise")
    )
    exclude_global = Q()

    for holiday in centre_holidays:
        if not holiday.file:
            continue
        stored_name = getattr(holiday.file, "name", "") or ""
        if not stored_name.strip():
            continue
        try:
            if not holiday.file.storage.exists(stored_name):
                continue
        except Exception:
            pass
        eff_state = effective_holiday_state(holiday)
        if not eff_state:
            continue
        exclude_global |= Q(
            category=DocumentCategory.HOLIDAY_LISTS,
            franchise__isnull=True,
            state=eff_state,
            academic_year=effective_holiday_academic_year(holiday),
        )
    if exclude_global:
        qs = qs.exclude(exclude_global)
    return qs


def _user_can_stream_parent_document(user, doc: ParentDocument) -> bool:
    """Parents: visible active docs. Franchise: global + own centre. Admin: all."""
    role = _norm_user_role(user)
    if role in (UserRole.ADMIN.value, UserRole.APPROVER.value):
        return True
    if not doc.is_active:
        return False
    if role == UserRole.PARENT.value:
        return _parent_documents_visible_queryset(user).filter(pk=doc.pk).exists()
    if role == UserRole.FRANCHISE.value:
        franchise = franchise_profile_for_user(user)
        if franchise is None:
            return False
        return doc.franchise_id is None or doc.franchise_id == franchise.id
    return False


@api_view(["GET"])
@authentication_classes([QueryJWTAuthentication])
@permission_classes([IsAuthenticated])
def parent_document_file(request, pk: int):
    """
    Stream a parent document file with JWT auth (header or ?access=), so browsers do not rely
    on public /media/… on the marketing domain.
    """
    doc = get_object_or_404(ParentDocument, pk=pk)
    if not _user_can_stream_parent_document(request.user, doc):
        raise PermissionDenied("You do not have access to this document.")
    if not doc.file:
        raise Http404("No file on this record.")
    try:
        file_handle = doc.file.open("rb")
    except FileNotFoundError:
        raise Http404("File missing on server.") from None
    stored_name = getattr(doc.file, "name", "") or ""
    content_type, _encoding = mimetypes.guess_type(stored_name)
    if not content_type:
        content_type = "application/octet-stream"
    fallback = parent_document_download_filename(doc)
    filename = safe_disposition_filename(request.GET.get("name"), fallback)
    return FileResponse(
        file_handle,
        as_attachment=False,
        content_type=content_type,
        filename=filename,
    )


def _franchise_hub_documents_queryset(franchise):
    """Active global + centre-specific franchise resource documents."""
    return (
        FranchiseDocument.objects.filter(is_active=True)
        .filter(Q(franchise=franchise) | Q(franchise__isnull=True))
        .select_related("franchise")
    )


def _hub_documents_for_franchise_user(user):
    """
    Centre documents: global HO uploads plus centre-specific rows when the login
    resolves to a franchise. Unlinked legacy logins still receive global documents.
    """
    franchise = franchise_profile_for_user(user)
    if franchise:
        return _franchise_hub_documents_queryset(franchise)
    return FranchiseDocument.objects.filter(is_active=True, franchise__isnull=True).select_related(
        "franchise"
    )


@api_view(["GET"])
@authentication_classes([QueryJWTAuthentication])
@permission_classes([IsFranchiseUser])
def franchise_document_file(request, pk: int):
    """
    Stream an active hub document file with JWT auth (avoids relying on public /media/… on the marketing domain).
    """
    doc = get_object_or_404(FranchiseDocument, pk=pk, is_active=True)
    if not _hub_documents_for_franchise_user(request.user).filter(pk=pk).exists():
        raise PermissionDenied("You do not have access to this document.")
    if not doc.file:
        raise Http404("No file on this record.")
    try:
        file_handle = doc.file.open("rb")
    except FileNotFoundError:
        raise Http404("File missing on server.") from None
    stored_name = getattr(doc.file, "name", "") or ""
    content_type, _encoding = mimetypes.guess_type(stored_name)
    if not content_type:
        content_type = "application/octet-stream"
    fallback = franchise_document_download_filename(doc)
    filename = safe_disposition_filename(request.GET.get("name"), fallback)
    resp = FileResponse(
        file_handle,
        as_attachment=False,
        content_type=content_type,
        filename=filename,
    )
    return resp


@api_view(["GET"])
@permission_classes([IsFranchiseUser])
def franchise_documents_all(request):
    """All franchise resource hub documents for the logged-in centre (all categories)."""
    documents = _hub_documents_for_franchise_user(request.user).order_by(
        "category", "order", "-created_at"
    )
    serializer = FranchiseDocumentSerializer(documents, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsFranchiseUser])
def franchise_documents_by_category(request, category: str):
    """
    Get franchise resource hub documents filtered by category.
    Returns franchise-specific documents and also global documents (franchise is null).
    """
    valid_categories = [choice[0] for choice in FranchiseDocumentCategory.choices]
    if category not in valid_categories:
        return Response({"error": "Invalid category"}, status=400)

    documents = _hub_documents_for_franchise_user(request.user).filter(category=category).order_by(
        "order", "-created_at"
    )

    serializer = FranchiseDocumentSerializer(documents, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAdminOrApproverUser])
def admin_franchise_documents_summary(request):
    """
    Per-category counts straight from FranchiseDocument (all rows).
    Includes every FranchiseDocumentCategory so HO can see empty buckets at a glance.
    """
    rows = list(
        FranchiseDocument.objects.values("category").annotate(
            total=Count("id"),
            active=Count("id", filter=Q(is_active=True)),
            with_file=Count("id", filter=~Q(file="")),
            with_embed=Count("id", filter=~Q(embed_url="")),
            with_content=Count("id", filter=Q(file__gt="") | ~Q(embed_url="")),
            global_count=Count("id", filter=Q(franchise__isnull=True)),
            centre_specific_count=Count("id", filter=Q(franchise__isnull=False)),
        )
    )
    by_cat = {r["category"]: r for r in rows}
    out = []
    for code, label in FranchiseDocumentCategory.choices:
        r = by_cat.get(code)
        total = int(r["total"]) if r else 0
        active = int(r["active"]) if r else 0
        with_file = int(r["with_file"]) if r else 0
        with_embed = int(r.get("with_embed", 0)) if r else 0
        with_content = int(r.get("with_content", 0)) if r else 0
        global_count = int(r["global_count"]) if r else 0
        centre_specific_count = int(r["centre_specific_count"]) if r else 0
        out.append(
            {
                "category": code,
                "category_display": str(label),
                "total": total,
                "active": active,
                "inactive": total - active,
                "with_file": with_file,
                "with_embed": with_embed,
                "missing_file": total - with_content,
                "global_count": global_count,
                "centre_specific_count": centre_specific_count,
            }
        )
    return Response(out)


class FranchiseParentDocumentListCreateView(generics.ListCreateAPIView):
    """Franchise: list parent-app documents; upload Newsletter and centre holiday PDFs."""

    permission_classes = [IsFranchiseUser]
    pagination_class = None
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return FranchiseParentDocumentWriteSerializer
        return ParentDocumentSerializer

    def get_queryset(self):
        franchise_profile = franchise_profile_for_user(self.request.user)
        if not franchise_profile:
            return ParentDocument.objects.none()
        manage = (self.request.query_params.get("manage") or "").strip().lower()
        if manage == "holidays":
            qs = ParentDocument.objects.filter(
                is_active=True,
                category=DocumentCategory.HOLIDAY_LISTS,
            ).filter(Q(franchise__isnull=True) | Q(franchise=franchise_profile))
            state = (self.request.query_params.get("state") or "").strip()
            if state:
                qs = qs.filter(state=state)
            return qs.select_related("franchise").order_by("-academic_year", "state", "-created_at")
        if manage == "newsletter":
            qs = ParentDocument.objects.filter(
                is_active=True,
                category=DocumentCategory.CLASS_TIMETABLE,
                franchise=franchise_profile,
            )
            track_date = (self.request.query_params.get("date") or "").strip()[:10]
            from_date = (self.request.query_params.get("from") or "").strip()[:10]
            to_date = (self.request.query_params.get("to") or "").strip()[:10]
            if track_date:
                qs = qs.filter(
                    Q(
                        period_start__isnull=False,
                        period_end__isnull=False,
                        period_start__lte=track_date,
                        period_end__gte=track_date,
                    )
                    | Q(
                        period_start__isnull=True,
                        period_end__isnull=True,
                        created_at__date=track_date,
                    )
                )
            elif from_date and to_date:
                qs = qs.filter(
                    Q(period_start__isnull=False, period_end__isnull=False, period_start__lte=to_date, period_end__gte=from_date)
                    | Q(
                        period_start__isnull=True,
                        period_end__isnull=True,
                        created_at__date__gte=from_date,
                        created_at__date__lte=to_date,
                    )
                )
            return qs.select_related("franchise").order_by("-period_start", "-created_at")
        return (
            ParentDocument.objects.filter(is_active=True)
            .filter(Q(franchise__isnull=True) | Q(franchise=franchise_profile))
            .select_related("franchise")
            .order_by("category", "order", "-created_at")
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doc = serializer.save()
        out = ParentDocumentSerializer(doc, context=self.get_serializer_context())
        return Response(out.data, status=status.HTTP_201_CREATED)


class FranchiseParentDocumentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Franchise: manage this centre's Newsletter and holiday list uploads."""

    permission_classes = [IsFranchiseUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return FranchiseParentDocumentWriteSerializer
        return ParentDocumentSerializer

    def get_queryset(self):
        franchise_profile = franchise_profile_for_user(self.request.user)
        if not franchise_profile:
            return ParentDocument.objects.none()
        return ParentDocument.objects.filter(
            franchise=franchise_profile,
            category__in=[DocumentCategory.CLASS_TIMETABLE, DocumentCategory.HOLIDAY_LISTS],
        ).select_related("franchise")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_destroy(self, instance):
        if instance.file:
            instance.file.delete(save=False)
        if instance.thumbnail:
            instance.thumbnail.delete(save=False)
        super().perform_destroy(instance)


class AdminParentDocumentListCreateView(generics.ListCreateAPIView):
    """Head office: list/create parent mobile app documents (global or per-centre)."""

    serializer_class = AdminParentDocumentSerializer
    permission_classes = [IsAdminOrApproverUser]
    pagination_class = None
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = ParentDocument.objects.all().select_related("franchise").order_by("category", "order", "-created_at")
        cat = (self.request.query_params.get("category") or "").strip()
        if cat:
            valid = [c[0] for c in DocumentCategory.choices]
            if cat in valid:
                qs = qs.filter(category=cat)
            else:
                return ParentDocument.objects.none()
        franchise_id = (self.request.query_params.get("franchise") or "").strip()
        if franchise_id == "global":
            qs = qs.filter(franchise__isnull=True)
        elif franchise_id.isdigit():
            qs = qs.filter(franchise_id=int(franchise_id))
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_create(self, serializer):
        serializer.save(is_active=True)


class AdminParentDocumentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Head office: retrieve, update, or delete a parent app document."""

    serializer_class = AdminParentDocumentSerializer
    permission_classes = [IsAdminOrApproverUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = ParentDocument.objects.all().select_related("franchise")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_destroy(self, instance):
        if instance.file:
            instance.file.delete(save=False)
        if instance.thumbnail:
            instance.thumbnail.delete(save=False)
        super().perform_destroy(instance)


class FranchiseCentreDocumentListCreateView(generics.ListCreateAPIView):
    """Legacy franchise centre hub bulk upload — restricted to admin (use admin/franchise-documents/)."""

    serializer_class = FranchiseCentreDocumentCreateSerializer
    permission_classes = [IsAdminOrApproverUser]
    pagination_class = None
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        franchise_profile = franchise_profile_for_user(self.request.user)
        if not franchise_profile:
            return FranchiseDocument.objects.none()
        return FranchiseDocument.objects.filter(franchise=franchise_profile).order_by(
            "category", "order", "-created_at"
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_create(self, serializer):
        franchise_profile = franchise_profile_for_user(self.request.user)
        if not franchise_profile:
            raise PermissionDenied("Franchise profile not found")
        serializer.save(franchise=franchise_profile, is_active=True)


class FranchiseCentreDocumentDetailView(generics.RetrieveDestroyAPIView):
    """Admin-only delete for legacy centre hub upload rows."""

    serializer_class = FranchiseDocumentSerializer
    permission_classes = [IsAdminOrApproverUser]
    queryset = FranchiseDocument.objects.all()

    def perform_destroy(self, instance):
        if instance.file:
            instance.file.delete(save=False)
        super().perform_destroy(instance)


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


class AdminFranchiseDocumentListCreateView(generics.ListCreateAPIView):
    """Head office: list/create franchise resource hub documents (global or per-centre)."""

    serializer_class = AdminFranchiseDocumentSerializer
    permission_classes = [IsAdminOrApproverUser]
    pagination_class = None
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = FranchiseDocument.objects.all().select_related("franchise").order_by("category", "order", "-created_at")
        cat = (self.request.query_params.get("category") or "").strip()
        if cat:
            valid = [c[0] for c in FranchiseDocumentCategory.choices]
            if cat in valid:
                qs = qs.filter(category=cat)
            else:
                return FranchiseDocument.objects.none()
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class AdminFranchiseDocumentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Head office: retrieve, update, or delete a franchise resource document."""

    serializer_class = AdminFranchiseDocumentSerializer
    permission_classes = [IsAdminOrApproverUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = FranchiseDocument.objects.all().select_related("franchise")

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_destroy(self, instance):
        if instance.file:
            instance.file.delete(save=False)
        super().perform_destroy(instance)


@api_view(["POST"])
@permission_classes([IsAdminOrApproverUser])
def admin_sync_pc_documents(request):
    """
    Import pc/ PDFs and public franchise images into FranchiseDocument (PostgreSQL).
    """
    root = getattr(settings, "PC_DOCUMENTS_ROOT", None)
    if not root:
        return Response(
            {"detail": "PC_DOCUMENTS_ROOT is not configured on the server."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    root_path = Path(root)
    if not root_path.is_dir():
        return Response(
            {"detail": f"PC folder not found: {root_path}"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        call_command("import_pc_documents", root=str(root_path.resolve()), update=True)
        call_command("import_franchise_public_assets", update=True)
    except Exception as exc:  # noqa: BLE001
        return Response(
            {"detail": f"Sync failed: {exc}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    total = FranchiseDocument.objects.count()
    return Response(
        {
            "detail": "All centre files and franchise images synced to the database.",
            "pc_root": str(root_path),
            "total_documents": total,
        },
        status=status.HTTP_200_OK,
    )

