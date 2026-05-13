"""
Reset passwords for migrated users whose `password` field is not a Django hash.

Why this exists:
- The migration script `migrate_um_system.py` inserts legacy password strings directly
  into the `users.password` column.
- Django authentication expects a hashed password in Django's format
  (e.g. `pbkdf2_sha256$...`). If the field contains legacy values, login will always fail.

Usage (from repo root):
  .\.venv\Scripts\python.exe scripts\reset_migrated_passwords.py --default "TimeKids@123"

Notes:
- This updates ONLY users whose password is not already a Django usable hash.
- This is intended for dev/staging after a dump/import.
"""

from __future__ import annotations

import argparse
import os
import sys


def _looks_like_django_hash(value: str) -> bool:
    # Django prefixes: algorithm$... (legacy dumps may also contain `$`, e.g. `plain$...`).
    alg = value.split("$", 1)[0].strip().lower()
    return alg in {
        "pbkdf2_sha256",
        "pbkdf2_sha1",
        "argon2",
        "bcrypt_sha256",
        "bcrypt",
        "scrypt",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--default", required=True, help="Default password to set on migrated users.")
    args = parser.parse_args()

    # Ensure backend repo root is importable when running as `python scripts/...`.
    backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "time4kids_be.settings")

    import django  # noqa: PLC0415

    django.setup()

    from accounts.models import User  # noqa: PLC0415

    default_password: str = args.default

    total = User.objects.count()
    updated = 0
    skipped = 0

    for u in User.objects.only("id", "email", "password").iterator():
        pw = (u.password or "").strip()
        if not pw:
            # Empty field -> definitely not authenticatable
            u.set_password(default_password)
            u.save(update_fields=["password"])
            updated += 1
            continue

        # Unusable marker
        if pw.startswith("!"):
            u.set_password(default_password)
            u.save(update_fields=["password"])
            updated += 1
            continue

        # If it already looks like a Django hash, leave it alone
        if _looks_like_django_hash(pw):
            skipped += 1
            continue

        # Legacy/plain/unknown format -> reset
        u.set_password(default_password)
        u.save(update_fields=["password"])
        updated += 1

    print(f"TOTAL={total} UPDATED={updated} SKIPPED={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

