import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "time4kids_be.settings")

import django

django.setup()

from students.legacy_fee_service import legacy_fee_connection

with legacy_fee_connection() as conn:
    cur = conn.cursor()
    for table, col in [("fee_payment", "idcard_no"), ("fee_amt_paid", "idcardno")]:
        cur.execute(
            f"SELECT COUNT(*) n FROM {table} WHERE {col} = %s",
            ("HYNK7103",),
        )
        print(table, "HYNK7103 count", cur.fetchone()["n"])

    cur.execute(
        "SELECT idcard_no, kid_name, centre_name FROM fee_payment WHERE kid_name LIKE %s LIMIT 5",
        ("%Sreeram%",),
    )
    print("fee by kid name Sreeram:", cur.fetchall())

    cur.execute("SHOW TABLES LIKE '%student%'")
    print("student tables:", [list(r.values())[0] for r in cur.fetchall()])
