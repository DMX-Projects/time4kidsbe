# -*- coding: utf-8 -*-
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def send_enquiry_email(enquiry):
    """
    Send email notification when a new enquiry is submitted.
    
    Args:
        enquiry: Enquiry instance with enquiry details
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    
    # Get SendGrid API key from settings
    api_key = getattr(settings, 'SENDGRID_API_KEY', None)
    if not api_key:
        logger.error("SendGrid API key not configured in settings")
        return False
    
    # Email addresses from settings
    from_email = getattr(settings, 'MAIL_FROM_ADDRESS', 'info@time4education.com')
    to_email = getattr(settings, 'MAIL_TO_ADDRESS', 'mdsahilkhan634@gmail.com')
    
    # Build recipient list
    recipients = [to_email]
    if enquiry.franchise and enquiry.franchise.contact_email:
        recipients.append(enquiry.franchise.contact_email)
    if enquiry.franchise and getattr(enquiry.franchise, "admin", None) and enquiry.franchise.admin.email:
        recipients.append(enquiry.franchise.admin.email)
    
    # Remove duplicates
    recipients = list(set(recipients))
    
    # Build email content
    subject = f'New {enquiry.enquiry_type.title()} Enquiry from {enquiry.name}'
    
    html_content = f'''
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
                <h2 style="margin: 0;">📬 New Enquiry Received - {enquiry.enquiry_type.title()}</h2>
            </div>
            <div class="content">
                <div class="field">
                    <div class="label">👤 Name:</div>
                    <div class="value">{enquiry.name}</div>
                </div>
                
                <div class="field">
                    <div class="label">📧 Email Address:</div>
                    <div class="value"><a href="mailto:{enquiry.email}">{enquiry.email}</a></div>
                </div>
                
                <div class="field">
                    <div class="label">📱 Phone Number:</div>
                    <div class="value">{enquiry.phone}</div>
                </div>
                
                <div class="field">
                    <div class="label">🏙️ City:</div>
                    <div class="value">{enquiry.city}</div>
                </div>
                
                {f'''
                <div class="field">
                    <div class="label">👶 Child Age:</div>
                    <div class="value">{enquiry.child_age}</div>
                </div>
                ''' if enquiry.child_age else ''}
                
                {f'''
                <div class="field">
                    <div class="label">🏢 Franchise:</div>
                    <div class="value">{enquiry.franchise.name}</div>
                </div>
                ''' if enquiry.franchise else ''}
                
                <div class="field">
                    <div class="label">💬 Message:</div>
                    <div class="value" style="white-space: pre-wrap;">{enquiry.message}</div>
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
    '''
    
    try:
        # Create email message
        message = Mail(
            from_email=from_email,
            to_emails=recipients,
            subject=subject,
            html_content=html_content
        )
        
        # Send email via SendGrid
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        
        # Check if successful (202 = Accepted)
        if response.status_code == 202:
            logger.info(f"Enquiry email sent successfully for: {enquiry.name} - Type: {enquiry.enquiry_type}")
            return True
        else:
            logger.warning(f"SendGrid returned status code: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending enquiry email: {str(e)}")
        return False


def send_franchise_enquiry_email(lead):
    """
    Send email when a new franchise opportunity lead is submitted (stored in `FranchiseEnquiry`).
    """
    api_key = getattr(settings, "SENDGRID_API_KEY", None)
    if not api_key:
        logger.error("SendGrid API key not configured in settings")
        return False

    from_email = getattr(settings, "MAIL_FROM_ADDRESS", "info@time4education.com")
    to_email = getattr(settings, "MAIL_TO_ADDRESS", "mdsahilkhan634@gmail.com")

    recipients = [to_email]
    if lead.franchise and lead.franchise.contact_email:
        recipients.append(lead.franchise.contact_email)
    if lead.franchise and getattr(lead.franchise, "admin", None) and lead.franchise.admin.email:
        recipients.append(lead.franchise.admin.email)

    recipients = list(set(recipients))

    subject = f"New Franchise Opportunity Lead from {lead.name}"

    html_content = f"""
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
                <h2 style="margin: 0;">📬 New Franchise Opportunity Lead</h2>
            </div>
            <div class="content">
                <div class="field">
                    <div class="label">👤 Name:</div>
                    <div class="value">{lead.name}</div>
                </div>
                <div class="field">
                    <div class="label">📧 Email:</div>
                    <div class="value"><a href="mailto:{lead.email}">{lead.email}</a></div>
                </div>
                <div class="field">
                    <div class="label">📱 Phone:</div>
                    <div class="value">{lead.phone}</div>
                </div>
                <div class="field">
                    <div class="label">🏙️ City:</div>
                    <div class="value">{lead.city}</div>
                </div>
                {f'''
                <div class="field">
                    <div class="label">🏢 Franchise:</div>
                    <div class="value">{lead.franchise.name}</div>
                </div>
                ''' if lead.franchise else ''}
                <div class="field">
                    <div class="label">💬 Details:</div>
                    <div class="value" style="white-space: pre-wrap;">{lead.message}</div>
                </div>
                <div class="footer">
                    <p style="margin-top: 15px; color: #999;">
                        This is an automated notification from T.I.M.E. Kids.
                    </p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        message = Mail(
            from_email=from_email,
            to_emails=recipients,
            subject=subject,
            html_content=html_content,
        )
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        if response.status_code == 202:
            logger.info(f"Franchise lead email sent for: {lead.name}")
            return True
        logger.warning(f"SendGrid returned status code: {response.status_code}")
        return False
    except Exception as e:
        logger.error(f"Error sending franchise lead email: {str(e)}")
        return False


LANDING_PARENT_SUBJECT = "Thank You for Your Interest in Timekids Preschool"
LANDING_PARENT_CC = "admissionleads@timekidspreschools.com"


def _render_landing_parent_body(record) -> str:
    centre_name = (record.centre_name or record.location or "").strip() or "—"
    centre_phone = (record.centre_phone or "").strip() or "—"
    centre_email = (record.centre_email or "").strip() or "—"
    return f"""Hi {record.name},<br><br>
Thank you for your interest in Timekids Preschool. We&rsquo;re delighted to connect with you.<br><br>
Please find below the details of your nearest centre :<br>
Centre Name : {centre_name}<br>
Contact Number : {centre_phone}<br>
Email ID : {centre_email}<br><br>
Please note that admissions are currently in progress and seats are limited.<br>
We encourage you to book a centre visit at the earliest to secure your child&rsquo;s admission.<br><br>
Our team will reach out to you shortly to assist you with admissions, curriculum details, and scheduling a visit to the centre.<br><br>
In the meantime, please feel free to contact the centre directly for any immediate queries.<br><br>
We look forward to being a part of your child&rsquo;s early learning journey.<br><br>
Warm regards,<br>Team Timekids"""


def _send_landing_parent_email(record, api_key: str, from_email: str) -> bool:
    from sendgrid.helpers.mail import Cc

    if not record.email:
        return False

    cc_list = getattr(settings, "MAIL_LANDING_CC", None) or LANDING_PARENT_CC
    cc_emails = [e.strip() for e in str(cc_list).split(",") if e.strip()]

    message = Mail(
        from_email=from_email,
        to_emails=record.email,
        subject=LANDING_PARENT_SUBJECT,
        html_content=_render_landing_parent_body(record),
    )
    for cc in cc_emails:
        message.add_cc(Cc(cc))

    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        if response.status_code == 202:
            logger.info("Landing thank-you email sent to %s", record.email)
            return True
        logger.warning("Landing parent email SendGrid status: %s", response.status_code)
        return False
    except Exception as e:
        logger.error("Landing parent email failed: %s", e)
        return False


def _send_landing_admin_email(record, api_key: str, from_email: str, to_email: str) -> bool:
    recipients = [to_email]
    if record.centre_email:
        recipients.append(record.centre_email)
    recipients = list({r for r in recipients if r})

    subject = f"New landing admission enquiry from {record.name}"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2>New landing page admission enquiry</h2>
        <p><strong>Name:</strong> {record.name}</p>
        <p><strong>Mobile:</strong> {record.mobileno}</p>
        <p><strong>Email:</strong> <a href="mailto:{record.email}">{record.email}</a></p>
        <p><strong>City:</strong> {record.city or "—"}</p>
        <p><strong>State:</strong> {record.state or "—"}</p>
        <p><strong>Location:</strong> {record.location or "—"}</p>
        <p><strong>Source:</strong> {record.source or "—"}</p>
        <p><strong>Centre:</strong> {record.centre_name or "—"}</p>
        <p><strong>Centre phone:</strong> {record.centre_phone or "—"}</p>
        <p><strong>Centre email:</strong> {record.centre_email or "—"}</p>
        <p style="color:#666;font-size:12px;">Automated notification from T.I.M.E. Kids landing pages.</p>
    </body>
    </html>
    """

    try:
        message = Mail(
            from_email=from_email,
            to_emails=recipients,
            subject=subject,
            html_content=html_content,
        )
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        if response.status_code == 202:
            logger.info("Landing admin email sent for enquiry id=%s", record.pk)
            return True
        logger.warning("Landing admin email SendGrid status: %s", response.status_code)
        return False
    except Exception as e:
        logger.error("Landing admin email failed: %s", e)
        return False


def send_landing_enquiry_emails(record) -> str:
    """
    Send parent thank-you + internal notification for a ``KidsEnquiry`` row.

    Returns: ``sent`` | ``partial`` | ``failed`` | ``skipped`` (no API key).
    """
    api_key = getattr(settings, "SENDGRID_API_KEY", None)
    if not api_key:
        logger.warning("SENDGRID_API_KEY not set; landing enquiry emails skipped")
        return "skipped"

    from_email = getattr(settings, "MAIL_FROM_ADDRESS", "info@time4education.com")
    to_email = getattr(settings, "MAIL_TO_ADDRESS", "mdsahilkhan634@gmail.com")

    parent_ok = _send_landing_parent_email(record, api_key, from_email)
    admin_ok = _send_landing_admin_email(record, api_key, from_email, to_email)

    if parent_ok and admin_ok:
        return "sent"
    if parent_ok or admin_ok:
        return "partial"
    return "failed"
