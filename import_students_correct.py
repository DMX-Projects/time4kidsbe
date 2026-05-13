
import re
import ast
import psycopg2

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


conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

print("Reading students...")

students1 = extract_rows("Student_details")
students2 = extract_rows("Student_details2")

students = students1 + students2

print(f"{len(students)} rows found")

parent_cache = {}

for row in students:

    try:

        sno = row[0]

        state = str(row[1]).strip() if row[1] else ""
        city = str(row[2]).strip() if row[2] else ""
        centre = str(row[3]).strip() if row[3] else ""

        student_name = str(row[4]).strip() if row[4] else ""
        class_name = str(row[5]).strip() if row[5] else ""
        roll_number = str(row[6]).strip() if row[6] else ""

        parent_name = str(row[9]).strip() if row[9] else ""

        email = str(row[10]).strip().lower() if row[10] else ""

        if not email:
            email = f"parent{sno}@timekids.local"

        phone = str(row[11]).strip() if row[11] else ""

        if not student_name:
            continue

        # ---------------------------------
        # GET FRANCHISE
        # ---------------------------------


        normalized_centre = centre.lower().replace(" ", "")

        cur.execute(
            """
            SELECT id
            FROM franchise
            WHERE LOWER(REPLACE(name, ' ', '')) = %s
            LIMIT 1
            """,
            (normalized_centre,)
        )


        franchise = cur.fetchone()

        if not franchise:
            continue

        franchise_id = franchise[0]

        # ---------------------------------
        # CREATE/FIND USER
        # ---------------------------------

        username = email

        cur.execute(
            """
            SELECT id
            FROM users
            WHERE username = %s
               OR email = %s
            LIMIT 1
            """,
            (username, email)
        )

        existing_user = cur.fetchone()

        if existing_user:

            user_id = existing_user[0]

        else:

            try:

                cur.execute(
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
                    VALUES
                    (
                        %s,%s,%s,%s,
                        TRUE,
                        'parent',
                        FALSE,
                        FALSE,
                        NOW()
                    )
                    RETURNING id
                    """,
                    (
                        username,
                        email,
                        "temp123",
                        parent_name
                    )
                )

                user_id = cur.fetchone()[0]

            except:

                conn.rollback()

                cur.execute(
                    """
                    SELECT id
                    FROM users
                    WHERE email = %s
                    LIMIT 1
                    """,
                    (email,)
                )

                existing_user = cur.fetchone()

                if not existing_user:
                    continue

                user_id = existing_user[0]

        # ---------------------------------
        # CREATE/FIND PARENT
        # ---------------------------------

        parent_key = f"{parent_name}_{phone}_{franchise_id}"

        if parent_key in parent_cache:

            parent_id = parent_cache[parent_key]

        else:

            cur.execute(
                """
                INSERT INTO franchises_parentprofile
                (
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
                VALUES
                (
                    %s,%s,NOW(),
                    %s,%s,%s,%s,%s,%s,FALSE
                )
                RETURNING id
                """,
                (
                    parent_name,
                    "",
                    franchise_id,
                    user_id,
                    phone[:10],
                    "",
                    city,
                    ""
                )
            )

            parent_id = cur.fetchone()[0]

            parent_cache[parent_key] = parent_id

        # ---------------------------------
        # PREVENT DUPLICATE STUDENTS
        # ---------------------------------

        cur.execute(
            """
            SELECT id
            FROM students_studentprofile
            WHERE roll_number = %s
            LIMIT 1
            """,
            (roll_number,)
        )

        existing_student = cur.fetchone()

        if existing_student:
            continue

        # ---------------------------------
        # CREATE STUDENT
        # ---------------------------------

        cur.execute(
            """
            INSERT INTO students_studentprofile
            (
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
            VALUES
            (
                %s,%s,%s,%s,
                NULL,
                NOW(),
                '',
                TRUE,
                NOW(),
                NOW(),
                %s,
                '',
                %s,
                ''
            )
            """,
            (
                student_name,
                "-",
                class_name,
                roll_number,
                parent_id,
                phone[:10]
            )
        )

        if sno % 1000 == 0:
            conn.commit()
            print(f"{sno} processed")

    except Exception as e:

        conn.rollback()

        print("ERROR:", e)

        continue

conn.commit()

cur.close()
conn.close()

print("DONE")

