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
    if enquiry.franchise and enquiry.franchise.admin.email:
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
