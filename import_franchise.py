
import re
import ast
import psycopg2
from psycopg2.extras import execute_values
from slugify import slugify

SQL_FILE = r"C:\Users\Admin1\Downloads\tkids\franchise.sql"

DB_CONFIG = {
    "dbname": "time4kids",
    "user": "postgres",
    "password": "123456",
    "host": "localhost",
    "port": "5432",
}


def extract_rows():
    rows = []

    with open(SQL_FILE, "r", encoding="latin-1", errors="ignore") as f:
        content = f.read()

    matches = re.findall(
        r"INSERT INTO `franchise`.*?VALUES\s*(\(.*?\));",
        content,
        re.S
    )

    for match in matches:

        raw_rows = re.findall(r"\(([^()]+)\)", match, re.S)

        for r in raw_rows:
            try:
                parsed = ast.literal_eval("(" + r + ")")
                rows.append(parsed)
            except:
                continue

    return rows


conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

print("Reading franchise rows...")
rows = extract_rows()

print(f"{len(rows)} rows found")

insert_rows = []

for row in rows:

    try:
        fid = row[0]

        fname = str(row[1]).strip() if row[1] else ""

        countryid = row[2]

        stateid = row[3]

        statename = str(row[4]).strip() if row[4] else ""

        cityid = row[5]

        cityname = str(row[6]).strip() if row[6] else ""

        areaid = row[7]

        areaname = str(row[8]).strip() if row[8] else ""

        address = str(row[9]).strip() if row[9] else ""

        phoneno = str(row[10]).strip() if row[10] else ""

        email = str(row[11]).strip() if row[11] else ""

        url = str(row[12]).strip() if row[12] else ""

        slug = slugify(fname)[:50]

        insert_rows.append(
            (
                fid,
                fname,
                slug,
                "",
                address,
                cityname,
                statename,
                "India",
                "",
                email,
                phoneno[:10],
                "",
                "",
                True,
                1,
                1,
                fname,
                countryid,
                stateid,
                statename,
                cityid,
                cityname,
                areaid,
                areaname,
                phoneno,
                email,
                url,
                "[]"
            )
        )

    except Exception:
        continue


execute_values(
    cur,
    """
    INSERT INTO franchise
    (
        id,
        name,
        slug,
        about,
        address,
        city,
        state,
        country,
        postal_code,
        contact_email,
        contact_phone,
        programs,
        facilities,
        is_active,
        admin_id,
        user_id,
        fname,
        countryid,
        stateid,
        statename,
        cityid,
        cityname,
        areaid,
        areaname,
        phoneno,
        email,
        url,
        school_program_cards
    )
    VALUES %s
    ON CONFLICT DO NOTHING
    """,
    insert_rows,
    page_size=1000
)

conn.commit()

cur.close()
conn.close()

print("Franchise import completed")

