import re
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


def parse_insert_values(table_name, filepath):

    pattern = re.compile(
        rf"INSERT INTO `{table_name}`.*?VALUES\s*(.*?);",
        re.S
    )

    with open(filepath, "r", encoding="latin-1", errors="replace") as f:
        content = f.read()

    matches = pattern.findall(content)

    rows = []

    for block in matches:

        entries = re.findall(r"\((.*?)\)", block, re.S)

        for e in entries:
            try:
                row = eval(f"({e})")
                rows.append(row)
            except:
                pass

    return rows


conn = psycopg2.connect(**PG)
cur = conn.cursor()

print("Reading states...")

states = parse_insert_values("states", OLD_SQL_FILE)

state_records = []
state_map = {}

for row in states:

    state_id = row[0]
    state_name = str(row[1]).strip()

    state_records.append((
        state_id,
        state_name
    ))

    state_map[state_id] = state_name

execute_values(
    cur,
    """
    INSERT INTO common_state (
        id,
        name
    )
    VALUES %s
    ON CONFLICT (id) DO NOTHING
    """,
    state_records
)

print(f"{len(state_records)} states inserted")

print("Reading cities...")

cities = parse_insert_values("cities", OLD_SQL_FILE)

city_records = []

for row in cities:

    city_id = row[0]
    city_name = str(row[1]).strip()
    state_name = str(row[4]).strip()

    state_id = None

    for sid, sname in state_map.items():

        if sname.lower() == state_name.lower():

            state_id = sid
            break

    if not state_id:
        continue

    city_records.append((
        city_id,
        state_id,
        city_name
    ))
execute_values(
    cur,
    """
    INSERT INTO common_city (
        id,
        state_id,
        name
    )
    VALUES %s
    ON CONFLICT (id) DO NOTHING
    """,
    city_records
)

print(f"{len(city_records)} cities inserted")

conn.commit()

cur.close()
conn.close()

print("DONE")