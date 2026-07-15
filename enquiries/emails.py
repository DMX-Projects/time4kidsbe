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
