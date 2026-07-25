"""Background Meta Lead Ads auto-sync (no manual cron required)."""

from __future__ import annotations

import logging
import os
import sys
import threading
import time

from django.conf import settings

logger = logging.getLogger(__name__)

_started = False
_lock = threading.Lock()


def _should_skip_process() -> bool:
    """Avoid starting during migrate/shell/tests or the runserver reloader parent."""
    if os.environ.get("RUN_MAIN") == "false":
        return True
    argv = [a.lower() for a in sys.argv[1:2]]
    blocked = {
        "migrate",
        "makemigrations",
        "test",
        "shell",
        "collectstatic",
        "createsuperuser",
        "sync_meta_leads",
        "check",
    }
    return bool(argv and argv[0] in blocked)


def _interval_seconds() -> int:
    configured = getattr(settings, "META_LEADS_AUTO_SYNC_SECONDS", None)
    if configured is not None:
        try:
            return max(60, int(configured))
        except (TypeError, ValueError):
            pass
    raw = os.getenv("META_LEADS_AUTO_SYNC_SECONDS") or "300"
    try:
        return max(60, int(raw))
    except (TypeError, ValueError):
        return 300


def _auto_sync_enabled() -> bool:
    flag = (os.getenv("META_LEADS_AUTO_SYNC") or "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    if flag in ("1", "true", "yes", "on"):
        return True
    # Default on when Page token is configured (production auto-sync).
    return bool((getattr(settings, "META_PAGE_ACCESS_TOKEN", "") or "").strip())


def _run_once() -> None:
    if not _lock.acquire(blocking=False):
        logger.info("Meta leads auto-sync skipped (already running)")
        return
    try:
        from .meta_leads import sync_page_leads

        summary = sync_page_leads(per_form_limit=20, max_forms=100)
        logger.info(
            "Meta leads auto-sync: forms=%s imported=%s skipped=%s failed=%s",
            summary.get("forms"),
            summary.get("imported"),
            summary.get("skipped"),
            summary.get("failed"),
        )
    except Exception:
        logger.exception("Meta leads auto-sync failed")
    finally:
        _lock.release()


def _loop() -> None:
    # Small delay so DB connections / app boot settle.
    time.sleep(20)
    while True:
        _run_once()
        time.sleep(_interval_seconds())


def start_meta_leads_autosync() -> None:
    global _started
    if _started or _should_skip_process() or not _auto_sync_enabled():
        return
    _started = True
    thread = threading.Thread(target=_loop, name="meta-leads-autosync", daemon=True)
    thread.start()
    logger.info(
        "Meta leads auto-sync started (every %ss). Set META_LEADS_AUTO_SYNC=0 to disable.",
        _interval_seconds(),
    )
