"""Build parent fee summary from Django FeeRecord rows (fallback when legacy DB unavailable)."""

from __future__ import annotations

from datetime import date
from typing import Any

from students.models import FeeRecord, StudentProfile


def _format_date(value) -> str:
    if not value:
        return "—"
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)


def _money(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _status_label(status: str, balance: float, due_date) -> str:
    normalized = (status or "").strip().upper()
    if normalized == "PAID" or balance <= 0:
        return "Paid"
    if normalized == "OVERDUE":
        return "Overdue"
    if due_date and hasattr(due_date, "year") and due_date < date.today():
        return "Overdue"
    return "Pending"


def build_fee_summary_from_records(student: StudentProfile, centre_name: str = "") -> dict[str, Any]:
    rows = list(
        FeeRecord.objects.filter(student=student)
        .order_by("due_date", "id")
    )
    first = rows[0] if rows else None
    enrollment = first.paid_on if first and first.paid_on else (first.due_date if first else None)

    lines: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        amount = _money(row.amount)
        discount = _money(row.discount)
        net = max(amount - discount, 0)
        paid = _money(row.amount_paid)
        if paid <= 0 and row.status == FeeRecord.Status.PAID:
            paid = net
        balance = max(net - paid, 0)
        lines.append(
            {
                "serial": idx,
                "fee_type": row.title,
                "total_fee": amount,
                "discount": discount,
                "net_payable": net,
                "amount_paid": paid,
                "balance": balance,
                "due_date": _format_date(row.due_date),
                "status": _status_label(row.status, balance, row.due_date),
            }
        )

    totals = {
        "total_fee": sum(_money(l["total_fee"]) for l in lines),
        "discount": sum(_money(l["discount"]) for l in lines),
        "net_payable": sum(_money(l["net_payable"]) for l in lines),
        "amount_paid": sum(_money(l["amount_paid"]) for l in lines),
        "balance": sum(_money(l["balance"]) for l in lines),
    }

    payments = []
    for row in rows:
        if row.paid_on and _money(row.amount_paid) > 0:
            payments.append(
                {
                    "amount_paid": _money(row.amount_paid),
                    "payment_type": row.title,
                    "mode_of_payment": "—",
                    "date_of_payment": _format_date(row.paid_on),
                    "fee_structure_name": row.fee_structure_name or "",
                }
            )

    return {
        "source": "records",
        "student": {
            "kid_name": student.full_name,
            "centre_name": centre_name or (student.Centre or "").strip(),
            "enrollment_date": _format_date(enrollment),
            "fee_structure_name": (first.fee_structure_name if first else "") or "",
            "id_card_no": (first.id_card_no if first else "") or (student.Idcardno or "").strip(),
            "course_name": (first.course if first else "") or (student.class_name or "").strip(),
        },
        "alerts": {
            "dropped_out": False,
            "drop_reason": "",
            "refund_done": False,
        },
        "lines": lines,
        "totals": totals,
        "payments": payments,
    }
