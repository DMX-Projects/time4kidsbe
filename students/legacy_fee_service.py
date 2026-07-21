"""Read parent fee details from legacy TiKES MySQL — ported from parent_homepage_viewstudentdetails.php."""

from __future__ import annotations

import logging
import os
import re
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pymysql

logger = logging.getLogger(__name__)


def legacy_fee_db_configured() -> bool:
    return bool(os.getenv("LEGACY_FEE_DB_HOST", "").strip())


def normalize_id_card_no(value: str | None) -> str:
    return (value or "").strip().upper()


def fetch_legacy_fee_summary(id_card_no: str) -> tuple[dict[str, Any] | None, str | None]:
    """Return (summary, error_message). error_message is set when summary is None."""
    normalized = normalize_id_card_no(id_card_no)
    if not normalized:
        return None, "Missing ID card number."

    if not legacy_fee_db_configured():
        return None, "Legacy fee database is not configured on the server."

    try:
        summary = build_legacy_fee_summary(normalized)
    except Exception as exc:
        # Don't dump full traceback every request — TiKES often unreachable from local/dev.
        logger.warning("Legacy fee lookup failed for %s: %s", normalized, exc)
        return None, f"Could not reach the TiKES fee database: {exc}"

    if not summary:
        return None, f"No active fee_payment records in TiKES for ID card {normalized}."

    return summary, None


def probe_legacy_fee_db(id_card_no: str = "") -> dict[str, Any]:
    """Quick connectivity check for ops scripts and debugging."""
    result: dict[str, Any] = {
        "configured": legacy_fee_db_configured(),
        "connected": False,
        "fee_payment_rows": None,
        "id_card_rows": None,
        "error": None,
    }
    if not result["configured"]:
        result["error"] = "LEGACY_FEE_DB_HOST is not set."
        return result

    normalized = normalize_id_card_no(id_card_no)
    try:
        with legacy_fee_connection() as conn:
            if conn is None:
                result["error"] = "Connection helper returned no connection."
                return result
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS n FROM fee_payment")
            result["fee_payment_rows"] = _int((cursor.fetchone() or {}).get("n"))
            result["connected"] = True
            if normalized:
                cursor.execute(
                    """
                    SELECT COUNT(*) AS n
                    FROM fee_payment
                    WHERE idcard_no = %s AND convert_status = '0'
                    """,
                    (normalized,),
                )
                result["id_card_rows"] = _int((cursor.fetchone() or {}).get("n"))
    except Exception as exc:
        logger.warning("Legacy fee DB probe failed: %s", exc, exc_info=True)
        result["error"] = str(exc)
    return result


@contextmanager
def legacy_fee_connection():
    host = os.getenv("LEGACY_FEE_DB_HOST", "").strip()
    if not host:
        yield None
        return
    conn = pymysql.connect(
        host=host,
        user=os.getenv("LEGACY_FEE_DB_USER", ""),
        password=os.getenv("LEGACY_FEE_DB_PASSWORD", ""),
        database=os.getenv("LEGACY_FEE_DB_NAME", "tikesin_bms"),
        port=int(os.getenv("LEGACY_FEE_DB_PORT", "3306")),
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        read_timeout=30,
        write_timeout=30,
    )
    try:
        yield conn
    finally:
        conn.close()


def _int(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(Decimal(str(value)))
    except Exception:
        return 0


def _format_date(value: Any) -> str:
    if value in (None, "", 0, "0"):
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    try:
        num = int(value)
        if num > 0:
            return datetime.fromtimestamp(num).strftime("%d/%m/%Y")
    except (TypeError, ValueError, OSError, OverflowError):
        pass
    return str(value).strip() or "—"


def _today_ts() -> int:
    return int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())


def _status_paid_overdue_pending(balance: int, due_ts: Any, *, waived: bool = False) -> str:
    if waived:
        return "Waived"
    if balance <= 0:
        return "Paid"
    try:
        due_num = int(due_ts or 0)
        if due_num > 0 and due_num < _today_ts():
            return "Overdue"
    except (TypeError, ValueError):
        pass
    return "Pending"


def _line(
    serial: int | str,
    fee_type: str,
    total_fee: int,
    discount: int,
    net_payable: int,
    amount_paid: int,
    balance: int,
    due_date: str,
    status: str,
) -> dict[str, Any]:
    return {
        "serial": serial,
        "fee_type": fee_type,
        "total_fee": total_fee,
        "discount": discount,
        "net_payable": net_payable,
        "amount_paid": amount_paid,
        "balance": balance,
        "due_date": due_date,
        "status": status,
    }


def _sum_special_discount(cursor, id_card_no: str) -> int:
    cursor.execute(
        """
        SELECT COALESCE(SUM(special_discount), 0) AS total_discount
        FROM fee_payment
        WHERE idcard_no = %s AND convert_status = '0'
        """,
        (id_card_no,),
    )
    row = cursor.fetchone() or {}
    return _int(row.get("total_discount"))


def _total_paid_till_date(cursor, id_card_no: str) -> int:
    cursor.execute(
        """
        SELECT COALESCE(SUM(amount_paid), 0) AS total
        FROM fee_amt_paid
        WHERE idcardno = %s
          AND payment_type NOT IN ('Transport Fee', 'Uniform Fee')
          AND (cheque_bounce_stuts IS NULL OR cheque_bounce_stuts != '1')
          AND (receipt_cancellation_status IS NULL OR receipt_cancellation_status != '1')
          AND (refund_fee_status IS NULL OR refund_fee_status != '1')
        """,
        (id_card_no,),
    )
    row = cursor.fetchone() or {}
    return _int(row.get("total"))


def _fetch_payments(cursor, id_card_no: str, centre_name: str) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT amount_paid, payment_type, mode_of_payment, date_of_payment, fee_structure_name
        FROM fee_amt_paid
        WHERE idcardno = %s
          AND centre_name = %s
          AND (cheque_bounce_stuts IS NULL OR cheque_bounce_stuts != '1')
          AND (receipt_cancellation_status IS NULL OR receipt_cancellation_status != '1')
          AND (refund_fee_status IS NULL OR refund_fee_status != '1')
        ORDER BY id ASC
        """,
        (id_card_no, centre_name),
    )
    rows = cursor.fetchall() or []
    return [
        {
            "amount_paid": _int(row.get("amount_paid")),
            "payment_type": (row.get("payment_type") or "—").strip() or "—",
            "mode_of_payment": (row.get("mode_of_payment") or "—").strip() or "—",
            "date_of_payment": _format_date(row.get("date_of_payment")),
            "fee_structure_name": (row.get("fee_structure_name") or "").strip(),
        }
        for row in rows
    ]


def _installment_amounts(installments_row: dict[str, Any], instalment_fee: int) -> tuple[int, int, int, int]:
    """Return (amount_paid_display, balance_display, ab, total_installments) like PHP."""
    ipayment_status = _int(installments_row.get("ipayment_status"))
    instal_remain_balance = installments_row.get("instal_remain_balance")
    ab = 0
    total_installments = instalment_fee
    paid_display = 0
    balance_display = 0

    if instal_remain_balance is not None and str(instal_remain_balance).strip() != "":
        total_installments = int(re.sub(r"-+", "", str(instalment_fee)))
        if total_installments <= instalment_fee:
            if ipayment_status == 1:
                total_installments = 0
                if total_installments == 0:
                    ab = total_installments
                    paid_display = instalment_fee
                else:
                    ab = total_installments
                    paid_display = total_installments
            else:
                total_installmentss = _int(instal_remain_balance)
                if total_installmentss == 0:
                    ab = total_installmentss
                    paid_display = instalment_fee
                else:
                    ab = total_installmentss
                    paid_display = instalment_fee - total_installmentss
        else:
            total_installmentss = instalment_fee - _int(instal_remain_balance)
            if ipayment_status == 1:
                total_installments = 0
                if total_installments == 0:
                    ab = total_installments
                    paid_display = instalment_fee
                else:
                    ab = total_installments
                    paid_display = instalment_fee - total_installments
            else:
                total_installmentss = _int(instal_remain_balance)
                if total_installmentss == 0:
                    ab = total_installmentss
                    paid_display = instalment_fee
                else:
                    ab = total_installmentss
                    paid_display = instalment_fee - total_installmentss
        balance_display = ab if instal_remain_balance is not None else 0
    else:
        total_installments = instalment_fee
        if total_installments == 0:
            ab = total_installments
            paid_display = instalment_fee
        else:
            ab = total_installments
            paid_display = instalment_fee - total_installments
        balance_display = total_installments

    return paid_display, balance_display, ab, total_installments


def _build_lumpsum_lines(
    row: dict[str, Any],
    fee_details_row: dict[str, Any],
    total_paid_till_date: int,
    special_discount_total: int,
    due_ts: Any,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    annualreg_fee = _int(fee_details_row.get("registration_fee")) + _int(fee_details_row.get("annual_fee"))
    term_fee = _int(fee_details_row.get("term_fee"))

    if annualreg_fee <= total_paid_till_date:
        remain_annuapaid = annualreg_fee
        remain_annualfee = total_paid_till_date - annualreg_fee
        bal_payble = 0
    else:
        remain_annualfee = 0
        remain_annuapaid = total_paid_till_date
        bal_payble = annualreg_fee - total_paid_till_date

    total_balance = _int(row.get("amount")) - total_paid_till_date
    total_balance_to_pay = total_balance - special_discount_total
    tfee = term_fee - special_discount_total - remain_annualfee

    lines = [
        _line(
            1,
            "Registration + Annual Fee",
            annualreg_fee,
            0,
            annualreg_fee,
            remain_annuapaid,
            bal_payble,
            _format_date(due_ts),
            _status_paid_overdue_pending(bal_payble, due_ts),
        ),
        _line(
            2,
            "Term Fee",
            term_fee,
            special_discount_total,
            term_fee - special_discount_total,
            remain_annualfee,
            tfee,
            _format_date(due_ts),
            _status_paid_overdue_pending(tfee, due_ts),
        ),
    ]
    totals = {
        "total_fee": _int(row.get("amount")),
        "discount": special_discount_total,
        "net_payable": _int(row.get("amount")) - special_discount_total,
        "amount_paid": remain_annualfee + remain_annuapaid,
        "balance": total_balance_to_pay,
    }
    return lines, totals


def _build_installment_lines(
    cursor,
    row: dict[str, Any],
    fee_details_row: dict[str, Any],
    row_fee_ann: dict[str, Any],
    centre_name: str,
    id_card_no: str,
    total_paid_till_date: int,
    special_discount_total: int,
    due_ts: Any,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    t_annual = _int(fee_details_row.get("annual_fee")) + _int(fee_details_row.get("registration_fee"))
    ann_discount = _int(row_fee_ann.get("special_discount"))
    annual_balance = _int(row_fee_ann.get("annual_amt_balance"))
    annual_paid = t_annual - ann_discount - annual_balance
    if annual_balance == 0:
        annual_balance_display = 0
    else:
        annual_balance_display = annual_balance

    if annual_balance == 0:
        if ann_discount != 0:
            annu = _int(fee_details_row.get("registration_fee")) + _int(fee_details_row.get("annual_fee"))
            if annu == ann_discount:
                annual_status = "Waived"
            else:
                annual_status = "Paid"
        else:
            annual_status = "Paid"
    else:
        annual_status = _status_paid_overdue_pending(annual_balance_display, due_ts)

    lines: list[dict[str, Any]] = [
        _line(
            1,
            "Registration + Annual Fee",
            t_annual,
            ann_discount,
            t_annual - ann_discount,
            annual_paid,
            annual_balance_display,
            _format_date(due_ts),
            annual_status,
        )
    ]

    count = 2
    insno = 1
    installmenttotal = 0

    cursor.execute(
        """
        SELECT installment_fee, special_discount, installment_after_discount, installment_date,
               ipayment_status, instal_remain_balance
        FROM fee_payment
        WHERE idcard_no = %s AND centre_name = %s
          AND payment_type != 'Lumpsum' AND convert_status = '0'
          AND installment_after_discount IS NOT NULL
        ORDER BY id ASC
        """,
        (id_card_no, centre_name),
    )
    installments = cursor.fetchall() or []

    for inst in installments:
        inst_fee = _int(inst.get("installment_fee"))
        inst_discount = _int(inst.get("special_discount")) if _int(inst.get("special_discount")) != 0 else 0
        inst_net = _int(inst.get("installment_after_discount"))
        inst_due = inst.get("installment_date")

        if _int(inst.get("ipayment_status")) == 1:
            waived = inst_fee == inst_discount and inst_fee > 0
            lines.append(
                _line(
                    count,
                    f"Installment {insno}",
                    inst_fee,
                    inst_discount,
                    inst_net,
                    inst_net,
                    0,
                    _format_date(inst_due),
                    "Waived" if waived else "Paid",
                )
            )
        else:
            paid_display, balance_display, ab, total_installments = _installment_amounts(inst, inst_net)
            installmenttotal += balance_display

            if total_installments == 0:
                status = "Waived"
            elif ab > 0:
                status = _status_paid_overdue_pending(ab, inst_due)
            else:
                status = "Paid"

            lines.append(
                _line(
                    count,
                    f"Installment {insno}",
                    inst_fee,
                    inst_discount,
                    inst_net,
                    paid_display,
                    balance_display,
                    _format_date(inst_due),
                    status,
                )
            )

        count += 1
        insno += 1

    cursor.execute(
        """
        SELECT amount_paid
        FROM miscellaneous_payment
        WHERE idcardno = %s
        ORDER BY id ASC
        """,
        (id_card_no,),
    )
    for misc in cursor.fetchall() or []:
        misc_paid = _int(misc.get("amount_paid"))
        if misc_paid <= 0:
            continue
        lines.append(
            _line("", "Miscellaneous Amount", 0, 0, 0, misc_paid, 0, "—", "Paid")
        )

    total_balance = _int(row.get("amount")) - total_paid_till_date
    total_balance_to_pay = total_balance - special_discount_total
    structure_total = (
        _int(fee_details_row.get("term_fee"))
        + _int(fee_details_row.get("registration_fee"))
        + _int(fee_details_row.get("annual_fee"))
    )
    tpaybal = structure_total - special_discount_total

    totals = {
        "total_fee": structure_total,
        "discount": special_discount_total,
        "net_payable": tpaybal,
        "amount_paid": tpaybal - total_balance_to_pay,
        "balance": installmenttotal,
    }
    return lines, totals


def build_legacy_fee_summary(id_card_no: str) -> dict[str, Any] | None:
    id_card_no = normalize_id_card_no(id_card_no)
    if not id_card_no:
        return None

    with legacy_fee_connection() as conn:
        if conn is None:
            return None
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT fee_structure_name
            FROM fee_payment
            WHERE idcard_no = %s AND convert_status = '1'
            GROUP BY enquiry_ref
            ORDER BY id DESC
            LIMIT 1
            """,
            (id_card_no,),
        )
        row_old = cursor.fetchone() or {}
        before_fee_structure = (row_old.get("fee_structure_name") or "").strip()

        cursor.execute(
            """
            SELECT actiondate, installment_date, enquiry_ref, idcard_no, amount, amount_paid,
                   kid_name, course_name, fee_structure_name, payment_type, centre_name, franchise_name
            FROM fee_payment
            WHERE idcard_no = %s AND convert_status = '0'
            GROUP BY enquiry_ref
            ORDER BY id ASC
            LIMIT 1
            """,
            (id_card_no,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        centre_name = (row.get("centre_name") or "").strip()
        franchise_name = (row.get("franchise_name") or "").strip()
        fee_structure_name = (row.get("fee_structure_name") or "").strip()

        cursor.execute(
            """
            SELECT student_drop_reason
            FROM fee_payment
            WHERE idcard_no = %s AND convert_status = '0' AND student_drop_status = '1'
            GROUP BY enquiry_ref
            LIMIT 1
            """,
            (id_card_no,),
        )
        drop_row = cursor.fetchone()

        cursor.execute(
            """
            SELECT id
            FROM fee_amt_paid
            WHERE idcardno = %s AND centre_name = %s AND refund_fee_status = '1'
            GROUP BY enquiry_ref
            LIMIT 1
            """,
            (id_card_no, centre_name),
        )
        refund_done = bool(cursor.fetchone())

        cursor.execute(
            """
            SELECT registration_fee, annual_fee, term_fee
            FROM fee_structure
            WHERE fee_structure_name = %s AND centre_name = %s AND franchise_name = %s
            LIMIT 1
            """,
            (fee_structure_name, centre_name, franchise_name),
        )
        fee_details_row = cursor.fetchone() or {}

        cursor.execute(
            """
            SELECT special_discount, annual_amt_balance
            FROM fee_payment
            WHERE idcard_no = %s AND convert_status = '0'
            ORDER BY id ASC
            LIMIT 1
            """,
            (id_card_no,),
        )
        row_fee_ann = cursor.fetchone() or {}

        cursor.execute(
            """
            SELECT date_of_payment
            FROM fee_amt_paid
            WHERE idcardno = %s AND centre_name = %s
            GROUP BY enquiry_ref
            ORDER BY id ASC
            LIMIT 1
            """,
            (id_card_no, centre_name),
        )
        row_fdate = cursor.fetchone() or {}

        total_paid_till_date = _total_paid_till_date(cursor, id_card_no)
        special_discount_total = _sum_special_discount(cursor, id_card_no)
        due_ts = row.get("installment_date")
        payment_type = (row.get("payment_type") or "").strip()

        if refund_done:
            lines: list[dict[str, Any]] = []
            totals = {
                "total_fee": 0,
                "discount": 0,
                "net_payable": 0,
                "amount_paid": 0,
                "balance": 0,
            }
        elif payment_type == "Lumpsum":
            lines, totals = _build_lumpsum_lines(
                row, fee_details_row, total_paid_till_date, special_discount_total, due_ts
            )
        else:
            lines, totals = _build_installment_lines(
                cursor,
                row,
                fee_details_row,
                row_fee_ann,
                centre_name,
                id_card_no,
                total_paid_till_date,
                special_discount_total,
                due_ts,
            )

        return {
            "source": "legacy",
            "payment_type": payment_type,
            "before_fee_structure": before_fee_structure,
            "student": {
                "kid_name": (row.get("kid_name") or "").strip(),
                "centre_name": centre_name,
                "enrollment_date": _format_date(row_fdate.get("date_of_payment")),
                "fee_structure_name": fee_structure_name,
                "id_card_no": id_card_no,
                "course_name": (row.get("course_name") or "").strip(),
            },
            "alerts": {
                "dropped_out": bool(drop_row),
                "drop_reason": (drop_row or {}).get("student_drop_reason") or "",
                "refund_done": refund_done,
            },
            "lines": lines,
            "totals": totals,
            "payments": _fetch_payments(cursor, id_card_no, centre_name),
        }
