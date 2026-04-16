#!/usr/bin/env python
"""
One-time helper: create or update two franchise centre logins (email + password).

1. Edit CENTERS below (real emails, passwords, names, slugs).
2. Ensure at least one Django superuser exists (HQ admin).
3. Run from time4kidsbe folder:
 python setup_two_franchise_centers.py

Franchise dashboard login uses EMAIL + PASSWORD (not username).
Do not commit real passwords; keep this file out of git if it holds secrets.
"""
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "time4kids_be.settings")
django.setup()

from django.utils.text import slugify

from accounts.models import User, UserRole
from franchises.models import Franchise

# --- Edit these two entries (slugs must stay unique across all franchises) ---
CENTERS = [
    {
        "email": "centre1@example.com",
        "password": "ChangeThisPassword1",
        "full_name": "Centre One Contact Name",
        "franchise_name": "T.I.M.E. Kids Centre One",
        "slug": "centre-one",
        "city": "",
    },
    {
        "email": "centre2@example.com",
        "password": "ChangeThisPassword2",
        "full_name": "Centre Two Contact Name",
        "franchise_name": "T.I.M.E. Kids Centre Two",
        "slug": "centre-two",
        "city": "",
    },
]


def main() -> None:
    hq_admin = User.objects.filter(is_superuser=True, is_active=True).first()
    if not hq_admin:
        print("No active superuser found. Run: python manage.py createsuperuser")
        sys.exit(1)

    for c in CENTERS:
        email = (c.get("email") or "").strip().lower()
        password = c.get("password") or ""
        if not email or not password:
            print(f"Skip: missing email or password for entry: {c!r}")
            continue
        if "example.com" in email:
            print(
                "Edit CENTERS in setup_two_franchise_centers.py "
                f"before running (still using placeholder email: {email})."
            )
            sys.exit(1)

        full_name = (c.get("full_name") or "").strip() or email.split("@")[0]
        franchise_name = (c.get("franchise_name") or "").strip() or full_name
        slug = (c.get("slug") or "").strip() or slugify(franchise_name)
        slug = slugify(slug) or slugify(email.split("@")[0])
        city = (c.get("city") or "").strip()

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "full_name": full_name,
                "role": UserRole.FRANCHISE,
            },
        )
        if not created and user.role != UserRole.FRANCHISE:
            user.role = UserRole.FRANCHISE
        user.full_name = full_name
        user.is_active = True
        user.set_password(password)
        user.save()

        franchise = getattr(user, "franchise_profile", None)
        if franchise is None:
            if Franchise.objects.filter(slug=slug).exclude(user=user).exists():
                print(f"Slug '{slug}' already taken; pick another slug for {email}.")
                sys.exit(1)
            franchise = Franchise.objects.create(
                admin=hq_admin,
                user=user,
                name=franchise_name,
                slug=slug,
                city=city,
                contact_email=email,
            )
            print(f"Created franchise: {franchise.name} ({email})")
        else:
            franchise.admin = hq_admin
            franchise.name = franchise_name
            franchise.city = city
            franchise.contact_email = email
            if franchise.slug != slug:
                if Franchise.objects.filter(slug=slug).exclude(pk=franchise.pk).exists():
                    print(f"Slug '{slug}' already taken; keeping slug '{franchise.slug}' for {email}.")
                else:
                    franchise.slug = slug
            franchise.save()
            print(f"Updated franchise: {franchise.name} ({email})")

    print("\nDone. Each centre logs in with its email and the password you set in CENTERS.")


if __name__ == "__main__":
    main()
