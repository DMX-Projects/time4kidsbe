"""Build parent fee summary from Django FeeRecord rows (fallback when legacy DB unavailable)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
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


def tikes_status_to_record_status(label: str) -> str:
    normalized = (label or "").strip().lower()
    if normalized in {"paid", "waived"}:
        return FeeRecord.Status.PAID
    if normalized == "overdue":
        return FeeRecord.Status.OVERDUE
    return FeeRecord.Status.PENDING


def parse_fee_due_date(value: str | None) -> date:
    s = (value or "").strip()
    if not s or s == "—":
        return date.today()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return date.today()


def _line_serial_key(serial: int | str | None) -> int:
    try:
        return int(serial or 0)
    except (TypeError, ValueError):
        return 0


def merge_centre_status_overrides(student: StudentProfile, summary: dict[str, Any]) -> dict[str, Any]:
    """Overlay centre-entered status (FeeRecord source=TIKES) onto TiKES/record fee lines."""
    lines = summary.get("lines") or []
    if not lines:
        return summary

    overrides = {
        fr.line_serial: fr
        for fr in FeeRecord.objects.filter(student=student, source=FeeRecord.Source.TIKES)
    }
    for line in lines:
        serial = _line_serial_key(line.get("serial"))
        override = overrides.get(serial)
        balance = _money(line.get("balance"))
        due_raw = line.get("due_date")
        due_date = parse_fee_due_date(due_raw if isinstance(due_raw, str) else None)
        if override:
            line["fee_record_id"] = override.id
            line["centre_status"] = override.status
            line["paid_on"] = override.paid_on.isoformat() if override.paid_on else None
            line["notes"] = override.notes or ""
            line["status"] = _status_label(override.status, balance, due_date)
        else:
            line["fee_record_id"] = line.get("fee_record_id")
            line["centre_status"] = tikes_status_to_record_status(line.get("status", ""))
            line.setdefault("paid_on", None)
            line.setdefault("notes", "")
    return summary


def fee_record_defaults_from_summary_line(
    student: StudentProfile,
    summary: dict[str, Any],
    line: dict[str, Any],
) -> dict[str, Any]:
    student_meta = summary.get("student") or {}
    total_fee = _money(line.get("total_fee"))
    discount = _money(line.get("discount"))
    net = _money(line.get("net_payable"))
    paid = _money(line.get("amount_paid"))
    if paid <= 0 and net <= 0:
        paid = total_fee - discount
    return {
        "source": FeeRecord.Source.TIKES,
        "line_serial": _line_serial_key(line.get("serial")),
        "title": (line.get("fee_type") or "").strip() or "Fee",
        "fee_structure_name": (student_meta.get("fee_structure_name") or "").strip(),
        "id_card_no": (student_meta.get("id_card_no") or "").strip() or (student.Idcardno or "").strip(),
        "course": (student_meta.get("course_name") or "").strip() or (student.class_name or "").strip(),
        "amount": Decimal(str(total_fee)),
        "discount": Decimal(str(discount)),
        "amount_paid": Decimal(str(paid)),
        "due_date": parse_fee_due_date(line.get("due_date")),
    }


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
                "fee_record_id": row.id,
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
    }
