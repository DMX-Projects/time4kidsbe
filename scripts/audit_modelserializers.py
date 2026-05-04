"""
Audit DRF ModelSerializers for Meta.fields that reference missing model fields.

This catches a common production 500 cause:
  - serializer Meta.fields includes "foo"
  - model does not have field "foo"
  - serializer also does not explicitly declare "foo"
DRF will raise at runtime when building/serializing the fields.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from pathlib import Path
import sys
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Finding:
    serializer: str
    model: str
    missing_field: str


def _iter_modules(package_name: str) -> Iterable[str]:
    try:
        pkg = importlib.import_module(package_name)
    except Exception:
        return []

    if not hasattr(pkg, "__path__"):
        return []

    for m in pkgutil.walk_packages(pkg.__path__, prefix=f"{package_name}."):
        yield m.name


def _model_field_names(model) -> set[str]:
    names: set[str] = set()
    for f in model._meta.get_fields():
        names.add(f.name)
    return names


def main() -> int:
    # Ensure settings are configured when running as a standalone script
    import os
    # Ensure project root is on sys.path (so `time4kids_be` imports work)
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "time4kids_be.settings")

    import django
    from django.apps import apps
    from rest_framework import serializers as drf_serializers

    django.setup()

    findings: list[Finding] = []

    for app_config in apps.get_app_configs():
        # Skip Django/contrib apps to keep noise down
        if app_config.name.startswith("django."):
            continue
        if app_config.name.startswith("rest_framework"):
            continue

        # Only scan each app's `serializers` module tree, if present
        base = f"{app_config.name}.serializers"
        module_names = [base, *list(_iter_modules(base))]

        for mod_name in module_names:
            try:
                mod = importlib.import_module(mod_name)
            except Exception:
                continue

            for _, obj in inspect.getmembers(mod, inspect.isclass):
                if not issubclass(obj, drf_serializers.ModelSerializer):
                    continue
                if obj is drf_serializers.ModelSerializer:
                    continue

                meta = getattr(obj, "Meta", None)
                model = getattr(meta, "model", None)
                fields = getattr(meta, "fields", None)

                if not model or not fields or fields == "__all__":
                    continue

                try:
                    model_fields = _model_field_names(model)
                except Exception:
                    continue

                declared = set(getattr(obj, "_declared_fields", {}).keys())
                # declared fields cover SerializerMethodField, source=..., etc.

                for f in fields:
                    if f in declared:
                        continue
                    if f in model_fields:
                        continue
                    # DRF also allows some non-model fields (like URL fields in HyperlinkedModelSerializer),
                    # but those are normally declared. Flag anything else.
                    findings.append(
                        Finding(
                            serializer=f"{obj.__module__}.{obj.__name__}",
                            model=f"{model.__module__}.{model.__name__}",
                            missing_field=f,
                        )
                    )

    if not findings:
        print("OK: No missing model fields referenced by ModelSerializers.")
        return 0

    print("FAIL: ModelSerializer Meta.fields includes missing model fields:\n")
    for it in sorted(findings, key=lambda x: (x.serializer, x.missing_field)):
        print(f"- {it.serializer} -> {it.model}: missing `{it.missing_field}`")
    print(f"\nTotal: {len(findings)}")
    return 2


if __name__ == "__main__":
    # Usage:
    #   python scripts/audit_modelserializers.py
    #
    # It expects to be run with:
    #   - CWD = time4kidsbe/
    #   - DJANGO_SETTINGS_MODULE = time4kids_be.settings (or manage.py default)
    sys.exit(main())

