"""Clear portal CMS + student data for Domalguda test parent (raviteja.k@time4education.com)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "time4kids_be.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models import Q

from accounts.profile_access import resolved_parent_profile_for_user
from documents.models import ParentDocument
from events.models import Event, EventMedia
from franchises.models import Franchise
from students.models import (
    Announcement,
    AnnouncementCampaign,
    AttendanceRecord,
    FeeRecord,
    HomeworkAssignment,
    ParentNotificationRead,
    StudentProfile,
    StudentTransportAssignment,
    SupportTicket,
    TransportRoute,
)

try:
    from students.models import ParentFeePayment
except ImportError:
    ParentFeePayment = None

TEST_PARENT_EMAIL = "raviteja.k@time4education.com"
TEST_FRANCHISE_USERNAME = "domalguda"


def _table_exists(name: str) -> bool:
    return name in connection.introspection.table_names()


def main():
    User = get_user_model()
    user = User.objects.filter(email__iexact=TEST_PARENT_EMAIL).first()
    if not user:
        print(f"Parent user not found: {TEST_PARENT_EMAIL}")
        sys.exit(1)

    pp = resolved_parent_profile_for_user(user)
    if not pp:
        print("Parent profile not found")
        sys.exit(1)

    franchise = pp.franchise
    if not franchise:
        fr = Franchise.objects.filter(username__iexact=TEST_FRANCHISE_USERNAME).first()
        if fr:
            franchise = fr
    if not franchise:
        print("Franchise not found")
        sys.exit(1)

    kid_ids = list(
        StudentProfile.objects.filter(parent=pp, is_active=True).values_list("pk", flat=True)
    )
    print(f"Parent profile: {pp.pk}")
    print(f"Franchise: {franchise.pk} ({franchise.name})")
    print(f"Children: {kid_ids}")

    stats = {}

    stats["homework"] = HomeworkAssignment.objects.filter(franchise=franchise).delete()[0]
    stats["announcements"] = Announcement.objects.filter(franchise=franchise).delete()[0]
    stats["announcement_campaigns"] = AnnouncementCampaign.objects.filter(
        franchise=franchise
    ).delete()[0]
    stats["attendance"] = AttendanceRecord.objects.filter(student_id__in=kid_ids).delete()[0]

    fee_qs = FeeRecord.objects.filter(student_id__in=kid_ids)
    fee_ids = list(fee_qs.values_list("pk", flat=True))
    stats["fee_payments"] = 0
    if fee_ids and _table_exists("payments_feepaymenttransaction"):
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM payments_feepaymenttransaction WHERE fee_record_id = ANY(%s)",
                [fee_ids],
            )
            stats["fee_payments"] = cursor.rowcount
    if ParentFeePayment and _table_exists("students_parentfeepayment"):
        stats["parent_fee_payments"] = ParentFeePayment.objects.filter(fee_record_id__in=fee_ids).delete()[0]
        stats["fees"] = fee_qs.delete()[0]
    elif fee_ids:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM students_feerecord WHERE student_id = ANY(%s)",
                [kid_ids],
            )
            stats["fees"] = cursor.rowcount
    else:
        stats["fees"] = 0
        stats["parent_fee_payments"] = 0
    stats["support_tickets"] = SupportTicket.objects.filter(parent=pp).delete()[0]
    stats["notification_reads"] = ParentNotificationRead.objects.filter(parent=pp).delete()[0]

    route_ids = list(
        TransportRoute.objects.filter(franchise=franchise).values_list("pk", flat=True)
    )
    stats["transport_assignments"] = StudentTransportAssignment.objects.filter(
        route_id__in=route_ids
    ).delete()[0]
    stats["transport_routes"] = TransportRoute.objects.filter(franchise=franchise).delete()[0]

    event_ids = list(Event.objects.filter(franchise=franchise).values_list("pk", flat=True))
    stats["event_media"] = EventMedia.objects.filter(event_id__in=event_ids).delete()[0]
    stats["events"] = Event.objects.filter(franchise=franchise).delete()[0]

    stats["parent_documents"] = ParentDocument.objects.filter(franchise=franchise).delete()[0]

    print("\nDeleted rows:")
    for key, count in stats.items():
        print(f"  {key}: {count}")
    print("\nDone. Students and parent login unchanged — upload fresh test data manually.")


if __name__ == "__main__":
    main()
