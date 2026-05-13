
import re
import ast
import psycopg2
from psycopg2.extras import execute_values

SQL_FILE = r"C:\timekids_migration\timepreschool_timekids.sql"

DB_CONFIG = {
    "dbname": "time4kids",
    "user": "postgres",
    "password": "123456",
    "host": "localhost",
    "port": "5432",
}


def extract_rows(table_name):
    rows = []

    with open(SQL_FILE, "r", encoding="latin-1", errors="ignore") as f:
        content = f.read()

    pattern = rf"INSERT INTO `{table_name}`.*?VALUES\s*(.*?);"
    matches = re.findall(pattern, content, re.S)

    for match in matches:
        raw_rows = re.findall(r"\((.*?)\)", match, re.S)

        for r in raw_rows:
            try:
                parsed = ast.literal_eval("(" + r + ")")
                rows.append(parsed)
            except:
                continue

    return rows


def map_role(group_id):
    if group_id == 1:
        return "admin"
    elif group_id == 5:
        return "parent"
    elif group_id == 6:
        return "franchise"
    return "user"


conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()


# -----------------------------
# MIGRATE GROUPS
# -----------------------------

print("Reading um_groups...")
groups = extract_rows("um_groups")

for row in groups:
    try:
        group_id = int(row[0])
        group_name = str(row[1]).strip()

        cur.execute(
            """
            INSERT INTO auth_group (id, name)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (group_id, group_name)
        )

    except:
        continue

print("Groups migrated")


# -----------------------------
# MIGRATE USERS
# -----------------------------

print("Reading um_users...")
users1 = extract_rows("um_users")

print("Reading um_users_new...")
users2 = extract_rows("um_users_new")

all_users = users1 + users2

unique_users = {}

for row in all_users:
    try:
        username = str(row[1]).strip() if row[1] else ""
        password = str(row[2]).strip() if row[2] else ""
        active = bool(row[4])
        email = str(row[10]).strip().lower() if row[10] else ""
        group_id = int(row[12]) if row[12] else 0

        if not username:
            continue

        key = email if email else username

        if key not in unique_users:
            unique_users[key] = (
                username,
                email,
                password,
                username,
                active,
                map_role(group_id),
                group_id
            )

    except:
        continue

print(f"{len(unique_users)} unique users found")

user_rows = list(unique_users.values())

execute_values(
    cur,
    """
    INSERT INTO users
    (
        username,
        email,
        password,
        full_name,
        is_active,
        role,
        is_staff,
        is_superuser,
        date_joined
    )
    VALUES %s
    ON CONFLICT DO NOTHING
    """,
    [
        (
            u[0],
            u[1],
            u[2],
            u[3],
            u[4],
            u[5],
            True if u[5] == "admin" else False,
            True if u[5] == "admin" else False,
            '2025-01-01'
        )
        for u in user_rows
    ],
    page_size=1000
)

print("Users migrated")


# -----------------------------
# USER GROUP MAPPING
# -----------------------------

print("Mapping users to groups...")

for u in user_rows:
    try:
        username = u[0]
        group_id = u[6]

        cur.execute(
            "SELECT id FROM users WHERE username = %s",
            (username,)
        )

        user = cur.fetchone()

        if not user:
            continue

        user_id = user[0]

        cur.execute(
            """
            INSERT INTO users_groups (user_id, group_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (user_id, group_id)
        )

    except:
        continue

print("User-group mapping done")


# -----------------------------
# USERASSIGNEDCENTERS
# -----------------------------

print("Reading UserAssignedCenters...")
assigned = extract_rows("UserAssignedCenters")

for row in assigned:
    try:
        assign_id, user_id, center_id = row

        cur.execute(
            """
            UPDATE franchise
            SET admin_id = %s,
                user_id = %s
            WHERE id = %s
            """,
            (user_id, user_id, center_id)
        )

    except:
        continue

print("UserAssignedCenters mapped")


# -----------------------------
# SCHOOL CENTERS
# -----------------------------

print("Reading school_centers...")
school_centers = extract_rows("school_centers")

for row in school_centers:
    try:
        center_id, center_name, user_id = row

        cur.execute(
            """
            UPDATE franchise
            SET admin_id = %s,
                user_id = %s
            WHERE id = %s
            """,
            (user_id, user_id, center_id)
        )

    except:
        continue

print("school_centers mapped")


# -----------------------------
# FRANCHISE CONVERSION
# -----------------------------

print("Reading franchisee_conversion...")
conv1 = extract_rows("franchisee_conversion")

print("Reading franchisee_conversion_18092021...")
conv2 = extract_rows("franchisee_conversion_18092021")

all_conv = conv1 + conv2

for row in all_conv:
    try:
        sno = row[0]
        refno = row[1]
        status = row[2]
        rating = row[3]
        comments = row[5]
        created_by = row[6]

        cur.execute(
            """
            INSERT INTO franchise_enquiry
            (
                id,
                notes
            )
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                sno,
                f"RefNo: {refno} | Status: {status} | Rating: {rating} | Comments: {comments} | Created By: {created_by}"
            )
        )

    except:
        continue

print("Franchise conversions migrated")

conn.commit()
cur.close()
conn.close()

print("DONE")

