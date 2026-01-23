from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def send_career_application_email(application):
    """
    Send email notification when a new career application is submitted.
    
    Args:
        application: JobApplication instance with career and applicant details
        
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
    
    # Build email content
    subject = f'New Career Application: {application.career.title}'
    
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: linear-gradient(135deg, #e6952e 0%, #dd6705 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
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
                <h2 style="margin: 0;">🎓 New Career Application Received</h2>
            </div>
            <div class="content">
                <div class="field">
                    <div class="label">📌 Position Applied For:</div>
                    <div class="value">{application.career.title} ({application.career.department})</div>
                </div>
                
                <div class="field">
                    <div class="label">👤 Applicant Name:</div>
                    <div class="value">{application.full_name}</div>
                </div>
                
                <div class="field">
                    <div class="label">📧 Email Address:</div>
                    <div class="value"><a href="mailto:{application.email}">{application.email}</a></div>
                </div>
                
                <div class="field">
                    <div class="label">📱 Phone Number:</div>
                    <div class="value">{application.phone}</div>
                </div>
                
                <div class="field">
                    <div class="label">🔗 LinkedIn Profile:</div>
                    <div class="value">
                        {f'<a href="{application.linkedin_url}" target="_blank">{application.linkedin_url}</a>' if application.linkedin_url else '<em>Not provided</em>'}
                    </div>
                </div>
                
                <div class="field">
                    <div class="label">📄 Resume:</div>
                    <div class="value">
                        {f'<strong>Attached to this email:</strong> {application.resume.name.split("/")[-1]}' if application.resume else '<em>Not uploaded</em>'}
                    </div>
                </div>
                
                <div class="field">
                    <div class="label">✍️ Cover Letter:</div>
                    <div class="value" style="white-space: pre-wrap;">
                        {application.cover_letter if application.cover_letter else '<em>Not provided</em>'}
                    </div>
                </div>
                
                <div class="footer">
                    <p><strong>Next Steps:</strong></p>
                    <ol>
                        <li>Review the attached resume</li>
                        <li>Read the cover letter and assess qualifications</li>
                        <li>Contact the candidate if suitable for interview</li>
                    </ol>
                    <p style="margin-top: 15px; color: #999;">
                        This is an automated notification from T.I.M.E. Kids Career Application System.
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
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )
        
        # Attach resume PDF if available
        if application.resume:
            try:
                import base64
                from sendgrid.helpers.mail import Attachment, FileContent, FileName, FileType, Disposition
                
                # Read the resume file
                resume_file = application.resume.open('rb')
                resume_data = resume_file.read()
                resume_file.close()
                
                # Encode to base64
                encoded_resume = base64.b64encode(resume_data).decode()
                
                # Get filename from the path
                filename = application.resume.name.split('/')[-1]
                
                # Create attachment
                attachment = Attachment(
                    FileContent(encoded_resume),
                    FileName(filename),
                    FileType('application/pdf'),
                    Disposition('attachment')
                )
                message.attachment = attachment
                
                logger.info(f"Resume attached: {filename}")
            except Exception as attach_error:
                logger.error(f"Error attaching resume: {str(attach_error)}")
                # Continue sending email even if attachment fails
        
        # Send email via SendGrid
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        
        # Check if successful (202 = Accepted)
        if response.status_code == 202:
            logger.info(f"Career application email sent successfully for: {application.full_name} - Position: {application.career.title}")
            return True
        else:
            logger.warning(f"SendGrid returned status code: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending career application email: {str(e)}")
        return False
