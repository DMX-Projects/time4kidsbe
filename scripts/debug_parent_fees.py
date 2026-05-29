import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "time4kids_be.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from students.legacy_fee_service import build_legacy_fee_summary, legacy_fee_connection
from students.models import StudentProfile

User = get_user_model()

print("Local students:", StudentProfile.objects.count())

ids_to_check = []
for u in User.objects.filter(role="PARENT")[:10]:
    ids_to_check.append((u.email, u.username or ""))

extra = ["HYAR0F01", "15032023"]
with legacy_fee_connection() as conn:
    cur = conn.cursor()
    for email, username in ids_to_check:
        cur.execute(
            "SELECT COUNT(*) AS n FROM fee_payment WHERE idcard_no = %s AND convert_status = '0'",
            (username,),
        )
        n = cur.fetchone()["n"]
        leg = build_legacy_fee_summary(username) if username else None
        lines = len(leg.get("lines") or []) if leg else 0
        print(f"{email} | username={username!r} | legacy_rows={n} | summary_lines={lines}")

    for i in extra:
        cur.execute(
            "SELECT COUNT(*) AS n FROM fee_payment WHERE idcard_no = %s AND convert_status = '0'",
            (i,),
        )
        print(f"extra {i}: legacy_rows={cur.fetchone()['n']}")
