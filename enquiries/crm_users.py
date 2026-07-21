"""CRM user labels for reports — real names, no Super Admin, no 'CRM ' prefix."""

from __future__ import annotations

from accounts.models import User, UserRole


def crm_users_queryset():
    """Active CRM users excluding Super Admin (manager login, not a lead handler)."""
    return (
        User.objects.filter(role__iexact=UserRole.CRM.value, is_active=True)
        .exclude(email__iexact="admin@timekids.com")
        .exclude(full_name__icontains="Super Admin")
        .order_by("id")
    )


def display_name_for_user(user: User) -> str:
    name = (user.full_name or "").strip()
    if name.lower().startswith("crm "):
        name = name[4:].strip()
    if name:
        return name
    email = (user.email or "").strip()
    if email:
        local = email.split("@")[0]
        if local.lower().startswith("crm."):
            local = local[4:]
        return local.replace(".", " ").strip() or email
    return f"User {user.id}"


def crm_user_label_map() -> dict[int, str]:
    """Map user id → display name."""
    return {user.id: display_name_for_user(user) for user in crm_users_queryset()}


def label_for_crm_user(user_id: int | None) -> str | None:
    if not user_id:
        return None
    user = User.objects.filter(pk=int(user_id)).first()
    if not user:
        return None
    return display_name_for_user(user)


def list_crm_users_for_api() -> list[dict]:
    return [
        {
            "id": user.id,
            "label": display_name_for_user(user),
            "fullName": display_name_for_user(user),
            "email": user.email,
        }
        for user in crm_users_queryset()
    ]


def assigned_user_payload(user) -> dict:
    if not user:
        return {"assignedUserId": None, "assignedUserLabel": None}
    return {
        "assignedUserId": user.id,
        "assignedUserLabel": display_name_for_user(user),
    }
