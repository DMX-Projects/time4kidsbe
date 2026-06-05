"""Parent fee UPI QR payment helpers (static QR / manual confirm until gateway integration)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from urllib.parse import quote

from django.conf import settings
from django.utils import timezone

from franchises.models import ParentProfile
from students.models import FeeRecord, ParentFeePayment, StudentProfile


def parent_fee_upi_settings() -> dict[str, str | Decimal | None]:
    fixed_raw = (getattr(settings, "PARENT_FEE_QR_FIXED_AMOUNT", None) or "").strip()
    qr_fixed_amount = None
    if fixed_raw:
        try:
            qr_fixed_amount = Decimal(fixed_raw).quantize(Decimal("0.01"))
            if qr_fixed_amount <= 0:
                qr_fixed_amount = None
        except Exception:
            qr_fixed_amount = None

    return {
        "upi_vpa": (getattr(settings, "PARENT_FEE_UPI_VPA", None) or "").strip(),
        "payee_name": (getattr(settings, "PARENT_FEE_UPI_PAYEE_NAME", None) or "T.I.M.E. Kids").strip(),
        "qr_image_url": (getattr(settings, "PARENT_FEE_QR_IMAGE_URL", None) or "").strip(),
        "qr_fixed_amount": qr_fixed_amount,
    }


def build_upi_pay_uri(*, vpa: str, payee_name: str, amount: Decimal, note: str) -> str:
    """Standard UPI deep link (works with most UPI QR scanners)."""
    amount_str = f"{float(amount):.2f}"
    params = [
        f"pa={quote(vpa, safe='')}",
        f"pn={quote(payee_name, safe='')}",
        f"am={amount_str}",
        "cu=INR",
        f"tn={quote(note[:80], safe='')}",
    ]
    return "upi://pay?" + "&".join(params)


def _line_balance(line: dict[str, Any]) -> Decimal:
    return Decimal(str(line.get("balance") or 0))


def resolve_payable_line(
    *,
    student: StudentProfile,
    parent: ParentProfile,
    summary: dict[str, Any],
    fee_record_id: int | None = None,
    line_serial: int | None = None,
    fee_type: str = "",
) -> tuple[dict[str, Any] | None, str]:
    lines = summary.get("lines") or []
    if fee_record_id:
        for line in lines:
            if line.get("fee_record_id") == fee_record_id:
                if _line_balance(line) <= 0:
                    return None, "This fee is already paid."
                return line, ""
        fr = FeeRecord.objects.filter(pk=fee_record_id, student=student).first()
        if not fr:
            return None, "Fee record not found."
        amount = Decimal(str(fr.amount)) - Decimal(str(fr.discount or 0))
        paid = Decimal(str(fr.amount_paid or 0))
        balance = max(amount - paid, Decimal("0"))
        if balance <= 0:
            return None, "This fee is already paid."
        return {
            "serial": 0,
            "fee_type": fr.title,
            "balance": float(balance),
            "fee_record_id": fr.id,
        }, ""

    if line_serial is None:
        return None, "Specify which fee to pay."
    fee_type_norm = (fee_type or "").strip()
    for line in lines:
        if int(line.get("serial") or 0) != int(line_serial):
            continue
        if fee_type_norm and (line.get("fee_type") or "").strip() != fee_type_norm:
            continue
        if _line_balance(line) <= 0:
            return None, "This fee is already paid."
        return line, ""
    return None, "Fee line not found."


def apply_paid_payments_to_summary(summary: dict[str, Any], student: StudentProfile, parent: ParentProfile) -> dict[str, Any]:
    """Adjust legacy summary lines from confirmed app payments (no FeeRecord row)."""
    if not summary.get("lines"):
        return summary

    payments = list(
        ParentFeePayment.objects.filter(
            student=student,
            parent=parent,
            status=ParentFeePayment.Status.PAID,
        ).order_by("paid_at", "id")
    )
    if not payments:
        return summary

    lines = summary.get("lines") or []
    online_payment_rows = []
    for pay in payments:
        if pay.fee_record_id:
            for line in lines:
                if line.get("fee_record_id") == pay.fee_record_id:
                    paid_amt = float(line.get("amount_paid") or 0) + float(pay.amount)
                    net = float(line.get("net_payable") or 0)
                    line["amount_paid"] = paid_amt
                    line["balance"] = max(net - paid_amt, 0)
                    line["status"] = "Paid" if line["balance"] <= 0 else line.get("status") or "Pending"
                    break
        else:
            for line in lines:
                if int(line.get("serial") or 0) != pay.line_serial:
                    continue
                if (line.get("fee_type") or "").strip() != (pay.fee_type or "").strip():
                    continue
                paid_amt = float(line.get("amount_paid") or 0) + float(pay.amount)
                net = float(line.get("net_payable") or 0)
                line["amount_paid"] = paid_amt
                line["balance"] = max(net - paid_amt, 0)
                line["status"] = "Paid" if line["balance"] <= 0 else line.get("status") or "Pending"
                break
        online_payment_rows.append(
            {
                "payment_id": pay.id,
                "amount_paid": float(pay.amount),
                "payment_type": pay.fee_type,
                "mode_of_payment": pay.mode_of_payment or "UPI QR",
                "date_of_payment": pay.paid_at.strftime("%d/%m/%Y") if pay.paid_at else timezone.localdate().strftime("%d/%m/%Y"),
                "fee_structure_name": "",
                "receipt_available": True,
            }
        )

    totals = summary.get("totals") or {}
    totals["amount_paid"] = sum(float(l.get("amount_paid") or 0) for l in lines)
    totals["balance"] = sum(float(l.get("balance") or 0) for l in lines)
    summary["totals"] = totals

    existing = summary.get("payments") or []
    if online_payment_rows:
        deduped_existing = []
        for row in existing:
            duplicate = False
            for online in online_payment_rows:
                same_type = (row.get("payment_type") or "").strip() == (online.get("payment_type") or "").strip()
                same_amount = abs(float(row.get("amount_paid") or 0) - float(online.get("amount_paid") or 0)) < 0.01
                same_date = (row.get("date_of_payment") or "") == (online.get("date_of_payment") or "")
                if same_type and same_amount and same_date:
                    duplicate = True
                    break
            if not duplicate:
                deduped_existing.append(row)
        existing = deduped_existing
    summary["payments"] = online_payment_rows + existing
    return summary


def build_parent_fee_receipt(payment: ParentFeePayment, parent: ParentProfile) -> dict[str, Any]:
    student = payment.student
    centre = ""
    if parent.franchise_id:
        centre = (parent.franchise.name or "").strip()
    if not centre:
        centre = (student.Centre or "").strip()

    parent_name = (student.ParentName or "").strip()
    if not parent_name and parent.user_id:
        try:
            parent_name = (parent.user.full_name or "").strip() or (parent.user.email or "")
        except Exception:
            parent_name = ""

    paid_at = payment.paid_at or payment.created_at
    local_paid = timezone.localtime(paid_at) if paid_at else timezone.localtime()

    return {
        "receipt_no": f"T4K-{payment.id:06d}",
        "transaction_ref": payment.transaction_ref,
        "payment_id": payment.id,
        "paid_at": local_paid.isoformat(),
        "paid_at_display": local_paid.strftime("%d %b %Y, %I:%M %p"),
        "centre_name": centre or "T.I.M.E. Kids",
        "student_name": student.full_name,
        "student_class": (student.class_name or "").strip(),
        "id_card_no": (student.Idcardno or "").strip(),
        "parent_name": parent_name,
        "fee_type": payment.fee_type,
        "amount": float(payment.amount),
        "amount_display": f"₹{float(payment.amount):.2f}",
        "mode_of_payment": payment.mode_of_payment or "UPI QR",
        "status": payment.status,
    }


def mark_fee_record_paid(fee_record: FeeRecord, amount: Decimal) -> None:
    today = timezone.localdate()
    fee_record.amount_paid = (Decimal(str(fee_record.amount_paid or 0)) + amount).quantize(Decimal("0.01"))
    net = Decimal(str(fee_record.amount)) - Decimal(str(fee_record.discount or 0))
    if fee_record.amount_paid >= net:
        fee_record.amount_paid = net
        fee_record.status = FeeRecord.Status.PAID
    fee_record.paid_on = today
    fee_record.save(update_fields=["amount_paid", "status", "paid_on", "updated_at"])
