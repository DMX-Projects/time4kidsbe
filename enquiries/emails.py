# -*- coding: utf-8 -*-
"""Enquiry emails — same SendGrid + from-address as landing; personal + team inboxes."""

from __future__ import annotations

import html
import logging

from common.form_emails import (
    centre_details_from_franchise,
    franchise_team_inbox,
    normalize_personal_email,
    send_form_email_pair,
    send_team_notification,
)
from common.sendgrid_email import default_from_email, send_sendgrid_message, sendgrid_api_key

logger = logging.getLogger(__name__)


def _franchise_extra_recipients(franchise) -> list[str]:
    extra: list[str] = []
    if franchise and getattr(franchise, "contact_email", None):
        extra.append(franchise.contact_email)
    if franchise and getattr(franchise, "admin", None) and franchise.admin.email:
        extra.append(franchise.admin.email)
    return extra


def _admin_enquiry_html(enquiry) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #085390 0%, #0a6bb5 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
            .content {{ background: #f9f9f9; padding: 20px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 8px 8px; }}
            .field {{ margin-bottom: 15px; }}
            .label {{ font-weight: bold; color: #085390; }}
            .value {{ margin-top: 5px; padding: 10px; background: white; border-left: 3px solid #e6952e; }}
            .footer {{ margin-top: 20px; padding-top: 15px; border-top: 2px solid #ddd; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin: 0;">📬 New Enquiry Received - {html.escape(enquiry.enquiry_type.title())}</h2>
            </div>
            <div class="content">
                <div class="field">
                    <div class="label">👤 Name:</div>
                    <div class="value">{html.escape(enquiry.name)}</div>
                </div>
                <div class="field">
                    <div class="label">📧 Email Address:</div>
                    <div class="value"><a href="mailto:{html.escape(enquiry.email)}">{html.escape(enquiry.email)}</a></div>
                </div>
                <div class="field">
                    <div class="label">📱 Phone Number:</div>
                    <div class="value">{html.escape(enquiry.phone or "")}</div>
                </div>
                <div class="field">
                    <div class="label">🏙️ City:</div>
                    <div class="value">{html.escape(enquiry.city or "")}</div>
                </div>
                {f'''
                <div class="field">
                    <div class="label">👶 Child Age:</div>
                    <div class="value">{html.escape(enquiry.child_age)}</div>
                </div>
                ''' if enquiry.child_age else ''}
                {f'''
                <div class="field">
                    <div class="label">🏢 Franchise:</div>
                    <div class="value">{html.escape(enquiry.franchise.name)}</div>
                </div>
                ''' if enquiry.franchise else ''}
                <div class="field">
                    <div class="label">💬 Message:</div>
                    <div class="value" style="white-space: pre-wrap;">{html.escape(enquiry.message or "")}</div>
                </div>
                <div class="footer">
                    <p><strong>Next Steps:</strong></p>
                    <ol>
                        <li>Review the enquiry details above</li>
                        <li>Contact the person within 24-48 hours</li>
                        <li>Follow up based on enquiry type</li>
                    </ol>
                    <p style="margin-top: 15px; color: #999;">
                        This is an automated notification from T.I.M.E. Kids Enquiry System.
                    </p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


def send_enquiry_email(enquiry) -> bool:
    """
    Admission/contact form (``/api/enquiries/submit/``):
    - **Personal:** thank-you → ``enquiry.email`` (admission uses its own template; contact uses landing)
    - **Team:** alert → ``MAIL_TO_ADDRESS`` + franchise contacts
    """
    centre_name, centre_phone, centre_email = centre_details_from_franchise(enquiry.franchise)
    enquiry_type = (getattr(enquiry, "enquiry_type", None) or "").upper()
    personal_template = "admission" if enquiry_type == "ADMISSION" else "landing"
    status = send_form_email_pair(
        personal_email=enquiry.email,
        parent_name=enquiry.name,
        centre_name=centre_name,
        centre_phone=centre_phone,
        centre_email=centre_email,
        team_subject=f"New {enquiry.enquiry_type.title()} Enquiry from {enquiry.name}",
        team_html=_admin_enquiry_html(enquiry),
        team_extra_recipients=_franchise_extra_recipients(enquiry.franchise),
        personal_template=personal_template,
    )
    if status in ("sent", "partial"):
        logger.info(
            "Enquiry emails %s for %s (personal=%s)",
            status,
            enquiry.name,
            normalize_personal_email(enquiry.email),
        )
        return True
    logger.warning("Enquiry emails failed or skipped (status=%s)", status)
    return False


def _admin_franchise_lead_html(lead) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #085390 0%, #0a6bb5 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
            .content {{ background: #f9f9f9; padding: 20px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 8px 8px; }}
            .field {{ margin-bottom: 15px; }}
            .label {{ font-weight: bold; color: #085390; }}
            .value {{ margin-top: 5px; padding: 10px; background: white; border-left: 3px solid #e6952e; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin: 0;">📬 New Franchise Opportunity Lead</h2>
            </div>
            <div class="content">
                <div class="field"><div class="label">👤 Name:</div><div class="value">{html.escape(lead.name)}</div></div>
                <div class="field"><div class="label">📧 Email:</div><div class="value">{html.escape(lead.email)}</div></div>
                <div class="field"><div class="label">📱 Phone:</div><div class="value">{html.escape(lead.phone or "")}</div></div>
                <div class="field"><div class="label">🏙️ City:</div><div class="value">{html.escape(lead.city or "")}</div></div>
                {f'<div class="field"><div class="label">🏢 Franchise:</div><div class="value">{html.escape(lead.franchise.name)}</div></div>' if lead.franchise else ''}
                <div class="field"><div class="label">💬 Details:</div><div class="value" style="white-space: pre-wrap;">{html.escape(lead.message or "")}</div></div>
            </div>
        </div>
    </body>
    </html>
    """


def _personal_franchise_ack_html(lead) -> str:
    safe_name = html.escape((lead.name or "").strip() or "there")
    return f"""
    <p>Hi {safe_name},</p>
    <p>Thank you for your interest in a Timekids Preschool franchise opportunity.</p>
    <p>We have received your enquiry and our team will contact you shortly.</p>
    <p>Warm regards,<br>Team Timekids</p>
    """


def send_franchise_enquiry_email(lead) -> bool:
    """Franchise opportunity form: personal ack + team alert."""
    personal = normalize_personal_email(lead.email)
    if not sendgrid_api_key():
        return False

    parent_ok = False
    if personal:
        parent_ok = send_sendgrid_message(
            to_emails=personal,
            subject="We received your franchise enquiry — Timekids",
            html_content=_personal_franchise_ack_html(lead),
            from_email=default_from_email(),
        )

    team_ok = send_team_notification(
        subject=f"New Franchise Opportunity Lead from {lead.name}",
        html_content=_admin_franchise_lead_html(lead),
        extra_recipients=_franchise_extra_recipients(lead.franchise),
        team_inbox_address=franchise_team_inbox(),
    )
    return parent_ok or team_ok


def _crm_lead_personal_ack_html(lead) -> str:
    """Thank-you to the person who submitted July LP / Meta / WB franchise forms."""
    safe_name = html.escape((getattr(lead, "full_name", None) or "").strip() or "there")
    return f"""
    <p>Hi {safe_name},</p>
    <p>Thank you for your interest in a <strong>T.I.M.E. Kids</strong> preschool franchise opportunity.</p>
    <p>We have received your enquiry and our franchise team will contact you shortly to discuss the next steps.</p>
    <p>Warm regards,<br>Team T.I.M.E. Kids</p>
    """


def _crm_lead_team_html(lead) -> str:
    """Internal alert with campaign lead details (same layout for all 3 July forms)."""
    source_label = lead_source_label_for_crm_lead(lead)
    page_type = (getattr(lead, "utm_source", None) or "").strip() or "—"
    campaign = (getattr(lead, "utm_campaign", None) or "").strip() or "—"
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #085390 0%, #0a6bb5 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
            .content {{ background: #f9f9f9; padding: 20px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 8px 8px; }}
            .field {{ margin-bottom: 15px; }}
            .label {{ font-weight: bold; color: #085390; }}
            .value {{ margin-top: 5px; padding: 10px; background: white; border-left: 3px solid #e6952e; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin: 0;">📬 New Franchise Campaign Lead — {html.escape(source_label)}</h2>
            </div>
            <div class="content">
                <div class="field"><div class="label">👤 Name:</div><div class="value">{html.escape(lead.full_name or "")}</div></div>
                <div class="field"><div class="label">📧 Email:</div><div class="value">{html.escape(lead.email or "")}</div></div>
                <div class="field"><div class="label">📱 Phone:</div><div class="value">{html.escape(lead.mobile or "")}</div></div>
                <div class="field"><div class="label">🗺️ State:</div><div class="value">{html.escape(lead.state or "—")}</div></div>
                <div class="field"><div class="label">🏙️ City:</div><div class="value">{html.escape(lead.city or lead.preferred_centre_location or "—")}</div></div>
                <div class="field"><div class="label">💰 Investment range:</div><div class="value">{html.escape(lead.investment_range or "—")}</div></div>
                <div class="field"><div class="label">📄 Page type:</div><div class="value">{html.escape(page_type)}</div></div>
                <div class="field"><div class="label">📣 Campaign:</div><div class="value">{html.escape(campaign)}</div></div>
                <div class="field"><div class="label">🔗 Source:</div><div class="value">{html.escape(source_label)}</div></div>
                <div class="field"><div class="label">🌐 Landing URL:</div><div class="value">{html.escape(lead.landing_page_url or "—")}</div></div>
                <div class="field"><div class="label">💬 Comments:</div><div class="value" style="white-space: pre-wrap;">{html.escape(lead.comments or "—")}</div></div>
            </div>
        </div>
    </body>
    </html>
    """


def send_crm_lead_enquiry_emails(lead) -> bool:
    """
    July LP / Meta / WB (and other CrmLead) form submit:
    - **Personal:** franchise thank-you → ``lead.email``
    - **Team:** alert → franchise inbox (MAIL_FRANCHISE_TO_ADDRESS)
    Same templates for all three campaign forms; source/campaign fields differ per page.
    """
    if not sendgrid_api_key():
        logger.warning("CrmLead emails skipped — SENDGRID_API_KEY not set")
        return False

    personal = normalize_personal_email(lead.email)
    parent_ok = False
    if personal:
        parent_ok = send_sendgrid_message(
            to_emails=personal,
            subject="Thank You for Your Interest in T.I.M.E. Kids Franchise",
            html_content=_crm_lead_personal_ack_html(lead),
            from_email=default_from_email(),
        )
    else:
        logger.warning("CrmLead personal thank-you skipped — no email on lead id=%s", getattr(lead, "pk", None))

    display_name = (lead.full_name or "").strip() or "Lead"
    source_label = lead_source_label_for_crm_lead(lead)
    team_ok = send_team_notification(
        subject=f"New Franchise Campaign Lead from {display_name} ({source_label})",
        html_content=_crm_lead_team_html(lead),
        team_inbox_address=franchise_team_inbox(),
    )
    if parent_ok or team_ok:
        logger.info(
            "CrmLead emails personal=%s team=%s for id=%s source=%s",
            parent_ok,
            team_ok,
            getattr(lead, "pk", None),
            getattr(lead, "source", None),
        )
        return True
    logger.warning("CrmLead emails failed for id=%s", getattr(lead, "pk", None))
    return False


def _landing_admin_html(record) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2>New landing page admission enquiry</h2>
        <p><strong>Name:</strong> {html.escape(record.name or "")}</p>
        <p><strong>Mobile:</strong> {html.escape(record.mobileno or "")}</p>
        <p><strong>Email:</strong> {html.escape(record.email or "")}</p>
        <p><strong>City:</strong> {html.escape(record.city or "—")}</p>
        <p><strong>State:</strong> {html.escape(record.state or "—")}</p>
        <p><strong>Location:</strong> {html.escape(record.location or "—")}</p>
        <p><strong>Source:</strong> {html.escape(record.source or "—")}</p>
        <p><strong>Centre:</strong> {html.escape(record.centre_name or "—")}</p>
        <p><strong>Centre phone:</strong> {html.escape(record.centre_phone or "—")}</p>
        <p><strong>Centre email:</strong> {html.escape(record.centre_email or "—")}</p>
        <p style="color:#666;font-size:12px;">Automated notification from T.I.M.E. Kids landing pages.</p>
    </body>
    </html>
    """


def crm_direct_from_email() -> str:
    """CRM Direct Contact — always From franchise@timekidspreschools.com."""
    from django.conf import settings

    return (
        getattr(settings, "CRM_DIRECT_FROM_EMAIL", None)
        or "franchise@timekidspreschools.com"
    ).strip() or "franchise@timekidspreschools.com"


def send_crm_direct_contact_email(*, to_email: str, subject: str, body: str) -> bool:
    """
    Send a follow-up to the lead From franchise@… via SendGrid.
    Returns True when SendGrid accepts the message.
    """
    to = normalize_personal_email(to_email) or (to_email or "").strip()
    if not to:
        logger.warning("CRM direct contact: no recipient email")
        return False
    if not sendgrid_api_key():
        logger.warning("CRM direct contact: SENDGRID_API_KEY not set")
        return False

    plain = (body or "").strip() or "Hello from T.I.M.E. Kids."
    subj = (subject or "").strip() or "T.I.M.E. Kids – Follow-up"
    html_content = (
        "<html><body style=\"font-family: Arial, sans-serif; line-height: 1.6; color: #333;\">"
        + html.escape(plain).replace("\n", "<br>\n")
        + "</body></html>"
    )
    return send_sendgrid_message(
        to_emails=to,
        subject=subj,
        plain_text_content=plain,
        html_content=html_content,
        from_email=crm_direct_from_email(),
    )


def _crm_admin_login_url() -> str:
    from django.conf import settings

    base = (getattr(settings, "PUBLIC_SITE_URL", None) or "").strip().rstrip("/")
    if not base:
        base = "https://www.timekidspreschools.in"
    return f"{base}/crm-admin/login"


def send_crm_heads_new_lead_reminder(
    *,
    name: str,
    lead_source: str,
    centre_name: str = "",
    state: str = "",
    city: str = "",
    phone: str = "",
    lead_email: str = "",
    lead_kind: str | None = None,
    preferred_to: str | None = None,
    ignore_city: bool = False,
) -> bool:
    """
    New-lead email routing:

    - To: covering Zonal Manager + covering Regional Manager(s) while unassigned
    - Managers are notified only after an explicit assignment
    - Cc: other covering zonal/regional heads + Jayesh

    Controlled by settings.CRM_NOTIFY_ALL_HANDLERS (False skips completely).
    """
    from django.conf import settings

    from .crm_users import resolve_new_lead_mail_recipients

    if not getattr(settings, "CRM_NOTIFY_ALL_HANDLERS", True):
        logger.info("CRM lead reminder skipped — CRM_NOTIFY_ALL_HANDLERS is disabled")
        return False

    to_emails, cc_emails = resolve_new_lead_mail_recipients(
        state or None,
        city or centre_name or None,
        preferred_to=preferred_to,
        lead_kind=lead_kind,
        ignore_city=ignore_city,
    )

    # Optional always-notify / head emails → Cc (never replace the manager To)
    seen = {e.casefold() for e in to_emails}
    seen.update(e.casefold() for e in cc_emails)

    def _add_cc(addr: str) -> None:
        email = (addr or "").strip()
        if email and email.casefold() not in seen:
            seen.add(email.casefold())
            cc_emails.append(email)

    zonal = (getattr(settings, "CRM_ZONAL_HEAD_EMAIL", None) or "").strip()
    regional = (getattr(settings, "CRM_REGIONAL_HEAD_EMAIL", None) or "").strip()
    for addr in (zonal, regional):
        _add_cc(addr)
    for addr in (getattr(settings, "CRM_LEAD_ALWAYS_NOTIFY_EMAILS", None) or []):
        _add_cc(addr or "")

    if not to_emails:
        logger.info(
            "CRM lead reminder skipped — no recipients for state=%r city=%r kind=%r",
            state,
            city or centre_name,
            lead_kind,
        )
        return False
    if not sendgrid_api_key():
        logger.warning("CRM heads reminder skipped — SENDGRID_API_KEY not set")
        return False

    display_name = (name or "").strip() or "—"
    source = (lead_source or "").strip() or "—"
    centre = (centre_name or "").strip() or "—"
    place_city = (city or "").strip() or centre
    place_state = (state or "").strip() or "—"
    phone_disp = (phone or "").strip() or "—"
    email_disp = (lead_email or "").strip() or "—"
    login_url = _crm_admin_login_url()
    subject = f"New CRM lead — {display_name} ({source})"
    plain = (
        "New lead received in your territory.\n\n"
        f"Name: {display_name}\n"
        f"Phone: {phone_disp}\n"
        f"Email: {email_disp}\n"
        f"Lead source: {source}\n"
        f"State: {place_state}\n"
        f"City / Centre: {place_city}\n\n"
        f"Login to CRM to check this lead:\n{login_url}\n"
    )
    safe_login = html.escape(login_url)
    html_content = f"""
    <html><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
      <p><strong>New lead received in your territory.</strong></p>
      <p>
        <strong>Name:</strong> {html.escape(display_name)}<br>
        <strong>Phone:</strong> {html.escape(phone_disp)}<br>
        <strong>Email:</strong> {html.escape(email_disp)}<br>
        <strong>Lead source:</strong> {html.escape(source)}<br>
        <strong>State:</strong> {html.escape(place_state)}<br>
        <strong>City / Centre:</strong> {html.escape(place_city)}
      </p>
      <p>Login to CRM to check this lead:<br>
        <a href="{safe_login}">{safe_login}</a>
      </p>
    </body></html>
    """
    ok = send_sendgrid_message(
        to_emails=to_emails,
        cc=cc_emails,
        subject=subject,
        plain_text_content=plain,
        html_content=html_content,
        from_email=default_from_email(),
    )
    if ok:
        logger.info(
            "CRM notify ok to=%s cc=%s state=%r city=%r source=%r kind=%r",
            to_emails,
            cc_emails,
            place_state,
            place_city,
            source,
            lead_kind,
        )
    return ok


def send_crm_lead_assignment_email(obj, *, assigned_by=None) -> bool:
    """Notify a territory handler after an authorized manager assigns a lead."""
    assigned = getattr(obj, "assigned_user", None)
    recipient = (getattr(assigned, "email", None) or "").strip()
    if not recipient:
        logger.warning("CRM assignment email skipped — assignee has no email")
        return False
    if not sendgrid_api_key():
        logger.warning("CRM assignment email skipped — SENDGRID_API_KEY not set")
        return False

    lead_name = (
        getattr(obj, "full_name", None)
        or getattr(obj, "name", None)
        or "Lead"
    )
    state = (getattr(obj, "state", None) or "").strip()
    city = (getattr(obj, "city", None) or "").strip()
    franchise = getattr(obj, "franchise", None)
    if franchise is not None:
        if not state:
            state = (
                getattr(franchise, "statename", None)
                or getattr(franchise, "state", None)
                or ""
            ).strip()
        if not city:
            city = (
                getattr(franchise, "cityname", None)
                or getattr(franchise, "city", None)
                or ""
            ).strip()

    assigner_name = (
        getattr(assigned_by, "full_name", None)
        or getattr(assigned_by, "email", None)
        or "CRM Zonal Manager"
    )
    login_url = _crm_admin_login_url()
    subject = f"CRM lead assigned to you — {lead_name}"
    plain = (
        f"A CRM lead has been assigned to you by {assigner_name}.\n\n"
        f"Lead: {lead_name}\n"
        f"State: {state or '—'}\n"
        f"City / Centre: {city or '—'}\n\n"
        f"Login to CRM to view and follow up:\n{login_url}\n"
    )
    safe_login = html.escape(login_url)
    html_content = f"""
    <html><body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
      <p><strong>A CRM lead has been assigned to you.</strong></p>
      <p>
        <strong>Assigned by:</strong> {html.escape(str(assigner_name))}<br>
        <strong>Lead:</strong> {html.escape(str(lead_name))}<br>
        <strong>State:</strong> {html.escape(state or "—")}<br>
        <strong>City / Centre:</strong> {html.escape(city or "—")}
      </p>
      <p>Login to CRM to view and follow up:<br>
        <a href="{safe_login}">{safe_login}</a>
      </p>
    </body></html>
    """
    ok = send_sendgrid_message(
        to_emails=[recipient],
        subject=subject,
        plain_text_content=plain,
        html_content=html_content,
        from_email=default_from_email(),
    )
    if ok:
        logger.info(
            "CRM assignment email sent to=%s lead=%s id=%s assigned_by=%s",
            recipient,
            type(obj).__name__,
            getattr(obj, "pk", None),
            getattr(assigned_by, "email", None),
        )
    return ok


def assign_and_notify_new_lead(obj, *, lead_source: str = "") -> bool:
    """
    Notify CRM users about a new lead without assigning it automatically.
    A Regional or Zonal Manager explicitly assigns it to a territory handler.
    Works for CrmLead, FranchiseEnquiry, Enquiry, and similar objects with state/city.
    """
    from .crm_users import is_meta_instant_form_lead, resolve_notify_lead_kind

    state = (getattr(obj, "state", None) or "").strip()
    city = (getattr(obj, "city", None) or "").strip()
    franchise = getattr(obj, "franchise", None)
    if franchise is not None:
        if not state:
            state = (
                getattr(franchise, "statename", None)
                or getattr(franchise, "state", None)
                or ""
            ).strip()
        if not city:
            try:
                from franchises.franchise_geo import effective_city

                city = (effective_city(franchise) or "").strip() or city
            except Exception:
                pass

    centre = (
        getattr(obj, "preferred_centre_location", None)
        or getattr(obj, "centre_name", None)
        or (franchise.name if franchise is not None else None)
        or city
        or ""
    )
    name = (
        getattr(obj, "full_name", None)
        or getattr(obj, "name", None)
        or ""
    )
    phone = (
        getattr(obj, "mobile", None)
        or getattr(obj, "mobileno", None)
        or getattr(obj, "phone", None)
        or ""
    )
    lead_email = getattr(obj, "email", None) or ""

    source = (lead_source or "").strip()
    if not source:
        if hasattr(obj, "source"):
            source = lead_source_label_for_crm_lead(obj)
        elif hasattr(obj, "enquiry_type"):
            source = lead_source_label_for_enquiry(obj)
        else:
            source = "CRM"

    lead_kind = resolve_notify_lead_kind(obj, source)

    assigned = getattr(obj, "assigned_user", None)
    preferred_to = (getattr(assigned, "email", None) or "").strip() or None

    # Meta Instant Forms have no city dropdown — notify / map RMs by state only.
    ignore_city = is_meta_instant_form_lead(obj)

    return send_crm_heads_new_lead_reminder(
        name=name,
        lead_source=source,
        centre_name=str(centre or ""),
        state=state,
        city=city or str(centre or ""),
        phone=str(phone or ""),
        lead_email=str(lead_email or ""),
        lead_kind=lead_kind,
        preferred_to=preferred_to,
        ignore_city=ignore_city,
    )


def lead_source_label_for_enquiry(enquiry) -> str:
    et = (getattr(enquiry, "enquiry_type", None) or "").strip().upper()
    if et == "ADMISSION":
        return "Admission"
    if et == "CONTACT":
        return "Contact"
    return et or "Enquiry"


def lead_source_label_for_crm_lead(lead) -> str:
    from .crm_api import is_google_ads_landing_url

    raw = (getattr(lead, "source", None) or "").strip().lower()
    url = (getattr(lead, "landing_page_url", None) or "").lower()
    utm_source = (getattr(lead, "utm_source", None) or "").strip().lower()
    utm_medium = (getattr(lead, "utm_medium", None) or "").strip().lower()
    is_wb = raw == "lp_wb" or "timekids-lp-wb" in url

    if is_wb:
        meta_hint = (
            utm_source == "facebook_lead_ads"
            or any(token in utm_source for token in ("meta", "facebook", "instagram"))
            or any(token in utm_medium for token in ("meta", "facebook", "instagram"))
        )
        if meta_hint:
            return "Ants_Meta"
        return "Ants_Google"

    if is_google_ads_landing_url(getattr(lead, "landing_page_url", None)):
        return "Google"
    mapping = {
        "web": "Website (CRM)",
        "website": "Website (CRM)",
        "fb": "Facebook",
        "facebook": "Facebook",
        "insta": "Instagram",
        "instagram": "Instagram",
        "july_lp": "Google",
        "july_meta": "META",
        "lp_wb": "Ants_Google",
        "google": "Google",
    }
    return mapping.get(raw, raw.replace("_", " ").title() or "Campaign")


def send_landing_enquiry_emails(record) -> str:
    """
    Landing page submit:
    - **Personal:** thank-you → ``record.email``
    - **Team:** alert → ``MAIL_TO_ADDRESS`` + centre email
    """
    centre_name = (record.centre_name or record.location or "").strip() or "—"
    centre_phone = (record.centre_phone or "").strip() or "—"
    centre_email = (record.centre_email or "").strip() or "—"

    extra = []
    if record.centre_email:
        extra.append(record.centre_email)

    return send_form_email_pair(
        personal_email=record.email or "",
        parent_name=record.name or "",
        centre_name=centre_name,
        centre_phone=centre_phone,
        centre_email=centre_email,
        team_subject=f"New landing admission enquiry from {record.name}",
        team_html=_landing_admin_html(record),
        team_extra_recipients=extra,
    )
