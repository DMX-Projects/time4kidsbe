"""
Reconcile PostgreSQL ``users`` with legacy MySQL ``um_users`` (source of truth).

* Match each ``um_users`` row to an existing Django user by (in order of evidence):
  primary key ``id``, ``email``, ``username``, or ``code`` (all must agree on one user).
* Restore ``username``, ``email``, ``group_id``, and ``role`` from ``group_id``.
* Keep existing ``pbkdf2_`` password hashes; otherwise re-hash using
  ``StudentProfile.Password`` when available.
* If no PostgreSQL user matches an ``um_users`` row, creates one when email and
  username are free (synthetic email ``um_<id>@reconcile.legacy.local`` when MySQL
  email is empty).

Environment (MySQL — legacy DB), defaults match common local imports::

    UM_DB_HOST=127.0.0.1
    UM_DB_PORT=3306
    UM_DB_NAME=tkids_temp
    UM_DB_USER=root
    UM_DB_PASSWORD=

PostgreSQL uses the active Django settings (``.env`` / ``DB_*``).

Requires: ``pip install pymysql``

Run from ``time4kidsbe``::

    python manage.py shell -c "exec(open('reconcile_users_from_um_users.py', encoding='utf-8').read())"
"""
from __future__ import annotations

import os
from collections import defaultdict
from typing import Any

import django
from django.conf import settings

if not settings.configured:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "time4kids_be.settings")
    django.setup()

try:
    import pymysql
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "reconcile_users_from_um_users.py requires PyMySQL. Install with: pip install pymysql"
    ) from exc

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import transaction, IntegrityError

from accounts.models import UserRole
from students.models import StudentProfile

User = get_user_model()

GROUP_ROLE = {
    1: UserRole.ADMIN.value,
    5: UserRole.FRANCHISE.value,
    6: UserRole.PARENT.value,
}

UM_SQL = """
SELECT
    id,
    username,
    password,
    code,
    active,
    last_login,
    last_session,
    blocked,
    tries,
    last_try,
    email,
    mask_id,
    group_id,
    activation_time,
    last_action
FROM um_users
"""


def _norm_email(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip().lower()
    return s or None


def _norm_username(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _norm_code(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _mysql_connect():
    return pymysql.connect(
        host=os.getenv("UM_DB_HOST", "127.0.0.1"),
        port=int(os.getenv("UM_DB_PORT", "3306")),
        user=os.getenv("UM_DB_USER", "root"),
        password=os.getenv("UM_DB_PASSWORD", ""),
        database=os.getenv("UM_DB_NAME", "tkids_temp"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def _role_for_group(group_id: Any) -> str | None:
    if group_id is None:
        return None
    try:
        gid = int(group_id)
    except (TypeError, ValueError):
        return None
    return GROUP_ROLE.get(gid)


def _load_student_password_maps() -> tuple[dict[str, str], dict[str, str]]:
    by_idcard: dict[str, str] = {}
    by_email: dict[str, str] = {}
    qs = StudentProfile.objects.exclude(Password__isnull=True).exclude(Password="").only(
        "Idcardno", "Emailid", "Password"
    )
    for sp in qs.iterator():
        plain = (sp.Password or "").strip()
        if not plain:
            continue
        ic = (sp.Idcardno or "").strip()
        if ic:
            by_idcard[ic] = plain
        em = _norm_email(sp.Emailid)
        if em and em not in by_email:
            by_email[em] = plain
    return by_idcard, by_email


def _resolve_plain_from_mysql_row(
    mysql_username: str | None,
    mysql_email: str | None,
    by_idcard: dict[str, str],
    by_email: dict[str, str],
) -> str | None:
    if mysql_username and mysql_username in by_idcard:
        return by_idcard[mysql_username]
    if mysql_email and mysql_email in by_email:
        return by_email[mysql_email]
    return None


def _resolve_plain_password(
    mysql_username: str | None,
    mysql_email: str | None,
    user,
    by_idcard: dict[str, str],
    by_email: dict[str, str],
) -> str | None:
    plain = _resolve_plain_from_mysql_row(mysql_username, mysql_email, by_idcard, by_email)
    if plain:
        return plain
    for key in (_norm_username(user.username),):
        if key and key in by_idcard:
            return by_idcard[key]
    for em in (_norm_email(user.email),):
        if em and em in by_email:
            return by_email[em]
    return None


def _is_django_pbkdf2(pw: str | None) -> bool:
    return bool(pw and pw.startswith("pbkdf2_"))


def _build_user_indexes():
    users = list(
        User.objects.all().only(
            "id",
            "email",
            "username",
            "password",
            "role",
            "group_id",
            "code",
        )
    )
    by_id = {u.pk: u for u in users}
    by_email: dict[str, list] = defaultdict(list)
    by_username: dict[str, list] = defaultdict(list)
    by_code: dict[str, list] = defaultdict(list)
    for u in users:
        em = _norm_email(u.email)
        if em:
            by_email[em].append(u)
        un = _norm_username(u.username)
        if un:
            by_username[un].append(u)
        cd = _norm_code(u.code)
        if cd:
            by_code[cd].append(u)
    return by_id, by_email, by_username, by_code


def _merge_users_into(candidates: dict[int, Any], users: list) -> None:
    for u in users:
        candidates[u.pk] = u


def _match_user(
    row: dict[str, Any],
    by_id: dict[int, Any],
    by_email: dict[str, list],
    by_username: dict[str, list],
    by_code: dict[str, list],
) -> tuple[Any | None, str | None]:
    """Return (User | None, conflict_reason | None)."""
    mysql_id = row.get("id")
    mysql_username = _norm_username(row.get("username"))
    mysql_email = _norm_email(row.get("email"))
    mysql_code = _norm_code(row.get("code"))

    candidates: dict[int, Any] = {}

    if mysql_id is not None:
        try:
            pk = int(mysql_id)
            u = by_id.get(pk)
            if u is not None:
                candidates[u.pk] = u
        except (TypeError, ValueError):
            pass

    if mysql_email:
        _merge_users_into(candidates, by_email.get(mysql_email, []))

    if mysql_username:
        _merge_users_into(candidates, by_username.get(mysql_username, []))

    if mysql_code:
        _merge_users_into(candidates, by_code.get(mysql_code, []))

    if not candidates:
        return None, None

    if len(candidates) > 1:
        return None, "cross_field_mismatch"

    return next(iter(candidates.values())), None


def _register_user(
    u: User,
    by_id: dict[int, Any],
    by_email: dict[str, list],
    by_username: dict[str, list],
    by_code: dict[str, list],
) -> None:
    by_id[u.pk] = u
    em = _norm_email(u.email)
    if em:
        by_email[em].append(u)
    un = _norm_username(u.username)
    if un:
        by_username[un].append(u)
    cd = _norm_code(u.code)
    if cd:
        by_code[cd].append(u)


def _synthetic_email(mysql_id: Any) -> str:
    return f"um_{mysql_id}@reconcile.legacy.local"


def _synthetic_username(mysql_id: Any) -> str:
    return f"umuser_{mysql_id}"


def main() -> None:
    by_id, by_email, by_username, by_code = _build_user_indexes()
    pw_idcard, pw_email = _load_student_password_maps()

    created_users_n = 0
    updated_users_n = 0
    unresolved_password_n = 0
    legacy_password_samples: list[str] = []
    duplicate_conflicts: list[str] = []

    conn = _mysql_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(UM_SQL)
            rows = cur.fetchall()
    finally:
        conn.close()

    print(f"Loaded {len(rows)} rows from MySQL um_users.")

    for row in rows:
        mysql_id = row.get("id")
        mysql_username = _norm_username(row.get("username"))
        mysql_email = _norm_email(row.get("email"))
        mysql_code = _norm_code(row.get("code"))
        try:
            mysql_group_id = int(row["group_id"]) if row.get("group_id") is not None else None
        except (TypeError, ValueError):
            mysql_group_id = None

        user, conflict = _match_user(row, by_id, by_email, by_username, by_code)
        if conflict:
            duplicate_conflicts.append(
                f"um_users id={mysql_id} conflict={conflict} "
                f"email={mysql_email!r} username={mysql_username!r} code={mysql_code!r}"
            )
            continue

        if user is None:
            candidate_email = mysql_email or _synthetic_email(mysql_id)
            norm_email = User.objects.normalize_email(candidate_email)
            if User.objects.filter(email__iexact=norm_email).exists():
                duplicate_conflicts.append(
                    f"um_users id={mysql_id} create skipped: email {norm_email!r} already exists"
                )
                continue

            candidate_username = mysql_username or _synthetic_username(mysql_id)
            if User.objects.filter(username=candidate_username).exists():
                duplicate_conflicts.append(
                    f"um_users id={mysql_id} create skipped: username {candidate_username!r} already exists"
                )
                continue

            target_role = _role_for_group(mysql_group_id) or UserRole.PARENT.value
            plain = _resolve_plain_from_mysql_row(
                mysql_username, mysql_email, pw_idcard, pw_email
            )

            with transaction.atomic():
                u = User(
                    email=norm_email,
                    username=candidate_username,
                    code=_norm_code(row.get("code")),
                    group_id=mysql_group_id,
                    role=target_role,
                    is_active=True,
                    is_staff=False,
                    is_superuser=False,
                    full_name="",
                )
                if plain:
                    u.password = make_password(plain)
                else:
                    u.set_unusable_password()
                try:
                    u.save()
                except IntegrityError:
                    duplicate_conflicts.append(
                        f"um_users id={mysql_id} create failed IntegrityError "
                        f"(email={norm_email!r} username={candidate_username!r})"
                    )
                    continue
                if not plain:
                    unresolved_password_n += 1

            _register_user(u, by_id, by_email, by_username, by_code)
            created_users_n += 1
            continue

        with transaction.atomic():
            u = User.objects.select_for_update().get(pk=user.pk)

            target_username = mysql_username
            target_email = mysql_email
            target_group_id = mysql_group_id
            target_role = _role_for_group(mysql_group_id)

            update_fields: list[str] = []

            if target_username and target_username != (u.username or ""):
                taken = User.objects.exclude(pk=u.pk).filter(username=target_username).exists()
                if taken:
                    duplicate_conflicts.append(
                        f"um_users id={mysql_id} username {target_username!r} already taken by another user"
                    )
                else:
                    u.username = target_username
                    update_fields.append("username")

            if target_email:
                norm_new = User.objects.normalize_email(target_email)
                curr_norm = User.objects.normalize_email(u.email) if u.email else ""
                if norm_new.lower() != (curr_norm or "").lower():
                    taken = User.objects.exclude(pk=u.pk).filter(email__iexact=norm_new).exists()
                    if taken:
                        duplicate_conflicts.append(
                            f"um_users id={mysql_id} email {norm_new!r} already taken by another user"
                        )
                    else:
                        u.email = norm_new
                        update_fields.append("email")

            if target_group_id is not None and target_group_id != u.group_id:
                u.group_id = target_group_id
                update_fields.append("group_id")

            if target_role is not None and target_role != u.normalized_role():
                u.role = target_role
                update_fields.append("role")

            if mysql_code is not None and mysql_code != (u.code or ""):
                u.code = mysql_code
                update_fields.append("code")

            current_pw = u.password or ""
            if not _is_django_pbkdf2(current_pw):
                plain = _resolve_plain_password(
                    mysql_username, mysql_email, u, pw_idcard, pw_email
                )
                if plain:
                    u.password = make_password(plain)
                    update_fields.append("password")
                else:
                    unresolved_password_n += 1
                    if len(legacy_password_samples) < 500:
                        legacy_password_samples.append(
                            f"PostgreSQL user id={u.pk} email={u.email!r} username={u.username!r} "
                            f"non-pbkdf2 password; no StudentProfile.Password match"
                        )

            if update_fields:
                u.save(update_fields=sorted(set(update_fields)))
                updated_users_n += 1

    print("--- reconcile_users_from_um_users (done) ---")
    print("Created users:", created_users_n)
    print("Updated users:", updated_users_n)
    print("Unresolved passwords:", unresolved_password_n)
    print("Duplicate conflicts:", len(duplicate_conflicts))

    if duplicate_conflicts:
        print("\n-- sample duplicate conflicts (up to 30) --")
        for line in duplicate_conflicts[:30]:
            print(line)

    if legacy_password_samples:
        print("\n-- sample unresolved passwords on existing users (up to 30) --")
        for line in legacy_password_samples[:30]:
            print(line)


main()
