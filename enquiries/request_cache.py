"""Request-scoped memoisation for read-only CRM lookups.

Inside ``request_cache_scope()`` repeated geo / scope lookups (franchise state
lists, city -> state code, territory city lists) are computed once per request
instead of once per lead row. Outside a scope, nothing is cached, so behaviour
is unchanged for every other caller.
"""

from __future__ import annotations

import contextvars
import functools
from contextlib import contextmanager

_CACHE: contextvars.ContextVar[dict | None] = contextvars.ContextVar("crm_request_cache", default=None)


@contextmanager
def request_cache_scope():
    if _CACHE.get() is not None:
        yield
        return
    token = _CACHE.set({})
    try:
        yield
    finally:
        _CACHE.reset(token)


def with_request_cache(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with request_cache_scope():
            return func(*args, **kwargs)

    return wrapper


def active_cache() -> dict | None:
    return _CACHE.get()


_MISSING = object()


def cached(key, compute):
    """Return ``compute()`` memoised under ``key`` when a scope is active."""
    cache = _CACHE.get()
    if cache is None:
        return compute()
    value = cache.get(key, _MISSING)
    if value is _MISSING:
        value = compute()
        cache[key] = value
    return value
