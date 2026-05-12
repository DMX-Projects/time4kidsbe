import re
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values

OLD_SQL_FILE = r"C:\timekids_migration\timepreschool_timekids.sql"

PG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "time4kids",
    "user": "postgres",
    "password": "123456",
}

def clean_phone(val):
    return re.sub(r"[^0-9]", "", str(val or ""))[:10]

def safe(val, max_len=None):
    s = str(val or "").strip()
    return s[:max_len] if max_len else s

def now():
    return datetime.now()

def parse_students(filepath):

    rows = []

    with open(filepath, "r", encoding="latin-1", errors="replace") as f:

        for line in f:

            line = line.strip()

            if line.startswith("("):

                try:

                    values = eval(line.rstrip(",;"))

                    if len(values) >= 13:

                        row = {
                            "Sno": values[0],
                            "State": values[1],
                            "City": values[2],
                            "Centre": values[3],
                            "StudentName": values[4],
                            "Class": values[5],
                            "Idcardno": values[6],
                            "Password": values[7],
                            "batch_num": values[8],
                            "ParentName": values[9],
                            "Emailid": values[10],
                            "Mobileno": values[11],
                            "Year": values[12],
                        }

                        rows.append(row)

                except:
                    pass

    return rows

conn = psycopg2.connect(**PG)
cur = conn.cursor()

print("Reading students table...")

rows = parse_students(OLD_SQL_FILE)

print(f"{len(rows)} rows found")

parent_ids = {}

parent_records = []
student_records = []

parent_id_counter = 1
student_id_counter = 1

for row in rows:

    student_name = safe(row.get("StudentName"), 100)

    class_name = safe(row.get("Class"), 50)

    roll_number = safe(row.get("Idcardno"), 50)

    phone = clean_phone(row.get("Mobileno"))

    city = safe(row.get("City"), 100)

    parent_key = phone or student_name

    if parent_key not in parent_ids:

        parent_records.append((
            parent_id_counter,
            student_name,
            "",
            now(),
            29,
            1,
            phone,
            "",
            city,
            "",
            False
        ))

        parent_ids[parent_key] = parent_id_counter
        parent_id_counter += 1

    parent_id = parent_ids[parent_key]

    student_records.append((
        student_id_counter,
        student_name,
        "",
        class_name,
        roll_number,
        None,
        now(),
        "",
        True,
        now(),
        now(),
        parent_id,
        "",
        phone,
        ""
    ))

    student_id_counter += 1

print("Inserting parent profiles...")

execute_values(
    cur,
    """
    INSERT INTO franchises_parentprofile (
        id,
        child_name,
        notes,
        created_at,
        franchise_id,
        user_id,
        phone,
        address,
        city,
        photo_url,
        notifications_muted
    )
    VALUES %s
    ON CONFLICT (id) DO NOTHING
    """,
    parent_records,
    page_size=500
)

print(f"{len(parent_records)} parent profiles inserted")

print("Inserting students...")

execute_values(
    cur,
    """
    INSERT INTO students_studentprofile (
        id,
        first_name,
        last_name,
        class_name,
        roll_number,
        date_of_birth,
        admission_date,
        profile_picture,
        is_active,
        created_at,
        updated_at,
        parent_id,
        blood_group,
        emergency_contact,
        section
    )
    VALUES %s
    ON CONFLICT (id) DO NOTHING
    """,
    student_records,
    page_size=500
)

print(f"{len(student_records)} students inserted")

conn.commit()

cur.close()
conn.close()

print("DONE")