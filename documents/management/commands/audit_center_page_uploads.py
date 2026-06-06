"""List centre-page checklist rows not yet uploaded to FranchiseDocument."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.core.management.base import BaseCommand

from documents.models import FranchiseDocument

NAV_PATH = (
    Path(__file__).resolve().parents[4]
    / "time4kids"
    / "config"
    / "franchise-center-page-nav.ts"
)


def normalize_source_path_key(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("/").lower()


def extract_legacy_pc_relative_path(href: str) -> str | None:
    trimmed = href.strip()
    if not trimmed:
        return None
    try:
        pathname = urlparse(trimmed).path if trimmed.startswith("http") else trimmed
        if not pathname:
            return None
        match = re.search(r"/uploads/pc/(.+)", pathname, re.I) or re.search(
            r"^/media/pc/(.+)", pathname, re.I
        )
        if not match:
            return None
        return unquote(match.group(1).replace("\\", "/"))
    except Exception:
        return None


def extract_public_franchise_relative_path(href: str) -> str | None:
    trimmed = href.strip()
    if not trimmed.startswith("/"):
        return None
    path = trimmed.split("?")[0].split("#")[0]
    if path.startswith("/franchise-artworks/") or path.startswith("/franchise-gallery/"):
        return path.lstrip("/")
    return None


def stable_row_key(link: dict) -> str:
    if link.get("rowKey"):
        return link["rowKey"]
    href = (link.get("href") or "").strip()
    return f"href:{href}" if href else f"link:{link['label']}"


def checklist_source_path(link: dict) -> str:
    row_key = stable_row_key(link).replace(":", "/")
    return f"checklist-row/{row_key}"


def parse_nav_links(text: str) -> list[dict]:
    lines = text.splitlines()
    current_top = ""
    current_group = ""
    current_nested = ""
    links: list[dict] = []

    top_re = re.compile(r'^\s+id:\s*"([^"]+)"')
    title_re = re.compile(r'^\s+title:\s*"([^"]+)"')

    i = 0
    while i < len(lines):
        line = lines[i]
        if top_re.match(line) and i + 1 < len(lines) and "title:" in lines[i + 1]:
            current_top = title_re.search(lines[i + 1]).group(1)  # type: ignore[union-attr]
            current_group = ""
            current_nested = ""
            i += 2
            continue

        group_match = re.match(r'^\s{12}title:\s*"([^"]+)"', line)
        if group_match and "nested" not in line:
            current_group = group_match.group(1)
            current_nested = ""

        nested_match = re.match(r'^\s{16,20}title:\s*"([^"]+)"', line)
        if nested_match:
            current_nested = nested_match.group(1)

        if re.match(r"^\s+\{\s*$", line) and i + 1 < len(lines) and "label:" in lines[i + 1]:
            block_lines = [line]
            i += 1
            while i < len(lines):
                block_lines.append(lines[i])
                if re.match(r"^\s+\},?\s*$", lines[i]):
                    break
                i += 1
            block = "\n".join(block_lines)
            label_m = re.search(r'label:\s*"([^"]+)"', block)
            if label_m and "href:" in block:
                admin_m = re.search(r'adminCategory:\s*"([^"]+)"', block)
                if admin_m:
                    href_m = re.search(r'href:\s*"([^"]+)"', block)
                    row_m = re.search(r'rowKey:\s*"([^"]+)"', block)
                    links.append(
                        {
                            "section": current_top,
                            "group": current_group or None,
                            "nested": current_nested or None,
                            "label": label_m.group(1),
                            "href": href_m.group(1) if href_m else "",
                            "adminCategory": admin_m.group(1),
                            "rowKey": row_m.group(1) if row_m else None,
                        }
                    )
        i += 1
    return links


def doc_ready(doc: FranchiseDocument | None) -> bool:
    if not doc or not doc.id:
        return False
    return bool(doc.file or doc.embed_url)


class Command(BaseCommand):
    help = "Audit centre-page checklist links vs uploaded FranchiseDocument rows."

    def handle(self, *args, **options):
        text = NAV_PATH.read_text(encoding="utf-8")
        links = parse_nav_links(text)

        by_source: dict[str, FranchiseDocument] = {}
        for doc in FranchiseDocument.objects.filter(is_active=True):
            if doc.source_path:
                by_source[normalize_source_path_key(doc.source_path)] = doc

        uploaded = []
        missing = []

        for link in links:
            paths = [checklist_source_path(link)]
            legacy = extract_legacy_pc_relative_path(link.get("href") or "")
            if legacy:
                paths.append(legacy)
            public = extract_public_franchise_relative_path(link.get("href") or "")
            if public:
                paths.append(public)

            matched = None
            for p in paths:
                doc = by_source.get(normalize_source_path_key(p))
                if doc_ready(doc):
                    matched = doc
                    break

            breadcrumb = " › ".join(
                x
                for x in [
                    link["section"],
                    link.get("group"),
                    link.get("nested"),
                    link["label"],
                ]
                if x
            )
            entry = {
                "breadcrumb": breadcrumb,
                "category": link["adminCategory"],
                "source_path": checklist_source_path(link),
            }
            if matched:
                uploaded.append({**entry, "doc_id": matched.id, "doc_title": matched.title})
            else:
                missing.append(entry)

        self.stdout.write(f"Total checklist links (with adminCategory): {len(links)}")
        self.stdout.write(f"Uploaded to database: {len(uploaded)}")
        self.stdout.write(f"Not uploaded yet: {len(missing)}")
        self.stdout.write("")

        # Group missing by section
        by_section: dict[str, list[dict]] = {}
        for m in missing:
            by_section.setdefault(m["breadcrumb"].split(" › ")[0], []).append(m)

        for section in sorted(by_section):
            rows = by_section[section]
            self.stdout.write(self.style.WARNING(f"\n## {section} ({len(rows)} missing)"))
            for row in rows:
                self.stdout.write(f"  - {row['breadcrumb']}")
