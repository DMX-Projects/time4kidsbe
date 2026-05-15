"""Serve legacy centre resource files from PC_DOCUMENTS_ROOT (mirrors old /uploads/pc/)."""

from __future__ import annotations

import mimetypes
import urllib.parse
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.views.decorators.http import require_http_methods


def _pc_root() -> Path:
    root = getattr(settings, "PC_DOCUMENTS_ROOT", None)
    if not root:
        raise Http404("PC documents folder is not configured")
    root = Path(root)
    if not root.is_dir():
        raise Http404("PC documents folder not found")
    return root.resolve()


def _safe_join(root: Path, relative: str) -> Path:
    rel = urllib.parse.unquote(relative).replace("\\", "/").strip("/")
    if not rel or ".." in rel.split("/"):
        raise Http404("Invalid path")
    target = (root / rel).resolve()
    if not str(target).startswith(str(root)):
        raise Http404("Invalid path")
    return target


def _resolve_pc_file(root: Path, relative: str) -> Path:
    target = _safe_join(root, relative)
    if target.is_file():
        return target

    parent = target.parent
    if parent.is_dir():
        wanted = target.name.lower()
        for entry in parent.iterdir():
            if entry.is_file() and entry.name.lower() == wanted:
                return entry

    raise Http404("File not found")


@require_http_methods(["GET", "HEAD"])
def serve_pc_upload(request, relative_path: str):
    """
    GET /media/pc/<relative_path>
    Files are read from settings.PC_DOCUMENTS_ROOT (e.g. C:\\Users\\...\\Desktop\\pc).
    """
    root = _pc_root()
    path = _resolve_pc_file(root, relative_path)
    content_type, _encoding = mimetypes.guess_type(str(path))
    return FileResponse(
        path.open("rb"),
        as_attachment=False,
        filename=path.name,
        content_type=content_type or "application/octet-stream",
    )
