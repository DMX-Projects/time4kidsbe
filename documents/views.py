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
from accounts.profile_access import franchise_profile_for_user, resolved_parent_profile_for_user, effective_franchise_for_parent
from .auth import QueryJWTAuthentication
from .download_names import (
    franchise_document_download_filename,
    parent_document_download_filename,
    safe_disposition_filename,
)
from .models import ParentDocument, DocumentCategory, FranchiseDocument, FranchiseDocumentCategory, IndentRequest
from .newsletter_dates import filter_newsletters_by_date
from .parent_document_mobile import parent_documents_api_response
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
        from students.portal_views import _parent_student_from_request

        profile = resolved_parent_profile_for_user(self.request.user)
        student = _parent_student_from_request(self.request, profile) if profile else None
        return _parent_documents_visible_queryset(self.request.user, student=student)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["merge_holiday_for_parent"] = True
        return ctx

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        payload = parent_documents_api_response(request, serializer.data)
        return Response(payload)


@api_view(['GET'])
@permission_classes([IsParentUser])
def parent_documents_by_category(request, category):
    """Get active documents filtered by category"""

    # Validate category (including HOLIDAY_LISTS)
    valid_categories = [choice[0] for choice in DocumentCategory.choices]
    if category not in valid_categories:
        return Response({"error": "Invalid category"}, status=400)

    from students.portal_views import _parent_student_from_request

    category_filter = _parent_document_category_filter(category)
    profile = resolved_parent_profile_for_user(request.user)
    student = _parent_student_from_request(request, profile) if profile else None
    documents = _parent_documents_visible_queryset(request.user, student=student).filter(
        category__in=category_filter
    )
    if category == DocumentCategory.CLASS_TIMETABLE:
        track_date = (request.query_params.get("date") or "").strip()[:10]
        if track_date:
            documents = filter_newsletters_by_date(documents, track_date=track_date)
        documents = documents.order_by("-period_start", "-created_at")
    elif category == DocumentCategory.HOLIDAY_LISTS:
        documents = documents.order_by("state", "-academic_year", "-updated_at")

    serializer = ParentDocumentSerializer(
        documents,
        many=True,
        context={"request": request, "merge_holiday_for_parent": True},
    )
    payload = parent_documents_api_response(request, serializer.data)
    return Response(payload)


def _norm_user_role(user) -> str:
    return str(getattr(user, "role", "") or "").strip().upper()


def _parent_document_category_filter(category: str) -> list[str]:
    """Legacy NEWSLETTERS rows are shown with CLASS_TIMETABLE (parent newsletter)."""
    if category == DocumentCategory.CLASS_TIMETABLE:
        return [DocumentCategory.CLASS_TIMETABLE, DocumentCategory.NEWSLETTERS]
    return [category]


def _parent_documents_visible_queryset(user, student=None):
    """Active parent-app documents visible to this parent (scope + class filter)."""
    from .parent_document_media import filter_parent_documents_by_media_type
    from .publish_targeting import filter_documents_for_parent

    qs = ParentDocument.objects.filter(is_active=True).select_related("franchise")
    role = _norm_user_role(user)
    if role == UserRole.PARENT.value:
        profile = resolved_parent_profile_for_user(user)
        if profile:
            franchise = effective_franchise_for_parent(profile)
            if franchise:
                qs = qs.filter(Q(franchise__isnull=True) | Q(franchise_id=franchise.id))
            else:
                qs = qs.filter(franchise__isnull=True)
            qs = filter_documents_for_parent(qs, profile, student=student)
        else:
            qs = qs.filter(franchise__isnull=True, publish_scope=ParentDocument.PublishScope.PAN_INDIA)
            qs = qs.exclude(category=DocumentCategory.HOLIDAY_LISTS)
    qs = filter_parent_documents_by_media_type(qs)
    return qs.order_by("category", "order", "-created_at")


def _apply_holiday_centre_overrides(qs, franchise_id):
    """
    Deprecated: parents receive both head-office and centre holiday rows; the app merges
    PDFs and manual dates client-side (newest PDF wins for the same state + year).
    """
    return qs


def _user_can_stream_parent_document(user, doc: ParentDocument, request=None) -> bool:
    """Parents: visible active docs. Franchise: global + own centre. Admin: all."""
    role = _norm_user_role(user)
    if role in (UserRole.ADMIN.value, UserRole.APPROVER.value):
        return True
    if not doc.is_active:
        return False
    if role == UserRole.PARENT.value:
        from students.portal_views import _parent_focus_student

        profile = resolved_parent_profile_for_user(user)
        student = _parent_focus_student(request, profile) if request and profile else None
        return _parent_documents_visible_queryset(user, student=student).filter(pk=doc.pk).exists()
    if role == UserRole.FRANCHISE.value:
        franchise = franchise_profile_for_user(user)
        if franchise is None:
            return False
        from .publish_targeting import document_matches_franchise

        return document_matches_franchise(doc, franchise)
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
    if not _user_can_stream_parent_document(request.user, doc, request=request):
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


@api_view(["GET"])
@authentication_classes([QueryJWTAuthentication])
@permission_classes([IsAuthenticated])
def parent_document_audio_file(request, pk: int):
    """Stream newsletter audio upload with JWT auth (header or ?access=)."""
    doc = get_object_or_404(ParentDocument, pk=pk)
    if not _user_can_stream_parent_document(request.user, doc, request=request):
        raise PermissionDenied("You do not have access to this document.")
    if not doc.audio_file:
        raise Http404("No audio file on this record.")
    try:
        file_handle = doc.audio_file.open("rb")
    except FileNotFoundError:
        raise Http404("Audio file missing on server.") from None
    stored_name = getattr(doc.audio_file, "name", "") or ""
    content_type, _encoding = mimetypes.guess_type(stored_name)
    if not content_type:
        content_type = "audio/mpeg"
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


def _filter_holiday_docs_by_track_date(qs, track_date: str):
    """Holiday CMS: show lists created or updated on the selected track date."""
    if not track_date:
        return qs
    return qs.filter(Q(created_at__date=track_date) | Q(updated_at__date=track_date))


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
        from .publish_targeting import filter_documents_for_franchise, franchise_documents_base_q

        manage = (self.request.query_params.get("manage") or "").strip().lower()
        if manage == "holidays":
            qs = ParentDocument.objects.filter(
                is_active=True,
                category=DocumentCategory.HOLIDAY_LISTS,
            ).filter(franchise_documents_base_q(franchise_profile))
            qs = filter_documents_for_franchise(qs.select_related("franchise"), franchise_profile)
            state = (self.request.query_params.get("state") or "").strip()
            if not state:
                from documents.state_utils import franchise_state_code

                state = franchise_state_code(franchise_profile) or ""
            if state:
                qs = qs.filter(state=state)
            return qs.order_by("-academic_year", "state", "-created_at")
        if manage == "newsletter":
            qs = ParentDocument.objects.filter(
                is_active=True,
                category=DocumentCategory.CLASS_TIMETABLE,
            ).filter(franchise_documents_base_q(franchise_profile))
            qs = filter_documents_for_franchise(qs.select_related("franchise"), franchise_profile)
            track_date = (self.request.query_params.get("date") or "").strip()[:10]
            from_date = (self.request.query_params.get("from") or "").strip()[:10]
            to_date = (self.request.query_params.get("to") or "").strip()[:10]
            qs = filter_newsletters_by_date(qs, track_date=track_date, from_date=from_date, to_date=to_date)
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
        if instance.audio_file:
            instance.audio_file.delete(save=False)
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
        qs = ParentDocument.objects.all().select_related("franchise")
        manage = (self.request.query_params.get("manage") or "").strip().lower()
        if manage == "holidays":
            qs = qs.filter(is_active=True, category=DocumentCategory.HOLIDAY_LISTS)
            state = (self.request.query_params.get("state") or "").strip()
            if state:
                qs = qs.filter(state=state)
            track_date = (self.request.query_params.get("date") or "").strip()[:10]
            qs = _filter_holiday_docs_by_track_date(qs, track_date)
            return qs.order_by("-academic_year", "state", "-updated_at")
        if manage == "newsletter":
            qs = qs.filter(is_active=True, category=DocumentCategory.CLASS_TIMETABLE)
            track_date = (self.request.query_params.get("date") or "").strip()[:10]
            from_date = (self.request.query_params.get("from") or "").strip()[:10]
            to_date = (self.request.query_params.get("to") or "").strip()[:10]
            qs = filter_newsletters_by_date(qs, track_date=track_date, from_date=from_date, to_date=to_date)
            return qs.order_by("-period_start", "-created_at")
        return qs.order_by("category", "order", "-created_at")
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

