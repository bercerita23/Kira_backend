import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from typing import Optional, Dict, Any
import logging
from app.config import settings

# Constants
SENDER = "Bercerita KIRA <dev-team@kiraclassroom.com>"
CONFIGURATION_SET = "ConfigSet"
AWS_REGION = "us-east-2"
CHARSET = "UTF-8"

# Email templates
EMAIL_CSS_STYLES = """
    body {
        font-family: Arial, sans-serif;
        background-color: #f9f9f9;
        color: #333;
        padding: 20px;
    }
    .container {
        max-width: 600px;
        margin: 0 auto;
        background-color: #ffffff;
        border-radius: 8px;
        padding: 30px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }
    .code {
        font-size: 20px;
        font-weight: bold;
        background-color: #f1f1f1;
        padding: 12px 20px;
        border-radius: 6px;
        display: inline-block;
        margin: 20px 0;
        letter-spacing: 2px;
    }
    .footer {
        margin-top: 30px;
        font-size: 14px;
        color: #777;
    }
    a {
        color: #2a7ae2;
        text-decoration: none;
    }
"""


def _get_ses_client():
    """Create and return an AWS SES client."""
    return boto3.client(
        'ses', 
        region_name=AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID, 
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
    )


def _send_email(email: str, subject: str, body_html: str) -> bool:
    """
    Send an email using AWS SES.
    
    Args:
        email: Recipient email address
        subject: Email subject
        body_html: HTML body content
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        client = _get_ses_client()
        response = client.send_email(
            Destination={'ToAddresses': [email]},
            Message={
                'Body': {
                    'Html': {
                        'Charset': CHARSET,
                        'Data': body_html,
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': subject,
                },
            },
            Source=SENDER,
        )
        logging.info(f"Email sent successfully to {email}")
        return True
    except ClientError as e:
        error_msg = e.response['Error']['Message']
        logging.error(f"Failed to send email to {email}: {error_msg}")
        return False


def _create_email_template(
    title: str,
    main_content: str,
    verification_link: str,
    button_text: str,
    code: Optional[str] = None,
    additional_info: str = ""
) -> str:
    """
    Create a standardized email HTML template.
    
    Args:
        title: Email title/heading
        main_content: Main content paragraph
        verification_link: Link for the action button
        button_text: Text for the action button
        code: Optional verification code to display
        additional_info: Additional information to include
        
    Returns:
        str: Complete HTML email template
    """
    current_year = datetime.now().year
    
    code_section = ""
    if code:
        code_section = f"""
        <p>Your verification code is:</p>
        <div class="code">{code}</div>
        """
    
    return f"""\
<html>
  <head>
    <style>
{EMAIL_CSS_STYLES}
    </style>
  </head>
  <body>
    <div class="container">
      <h1>{title}</h1>
      <p>{main_content}</p>
      
      {code_section}
      {additional_info}
      <a href="{verification_link}" style="display:inline-block;margin-top:16px;padding:12px 24px;background:#2a7ae2;color:#fff;border-radius:6px;text-decoration:none;">{button_text}</a>
      <p>If the link does not work, you can copy and paste the following URL into your browser:</p>
      <p><a href="{verification_link}">{verification_link}</a></p>
      <div class="footer">
        <p>Learn more about us at <a href="https://www.bercerita.org/" target="_blank">bercerita.org</a>.</p>
        <p>&copy; {current_year} Bercerita KIRA. All rights reserved.</p>
      </div>
    </div>
  </body>
</html>
"""

def _create_email_template_without_button(
    title: str,
    main_content: str,
    verification_link: str,
    additional_info: str = ""
) -> str:
    """
    Create a standardized email HTML template.
    
    Args:
        title: Email title/heading
        main_content: Main content paragraph
        verification_link: Link for the action button
        button_text: Text for the action button
        code: Optional verification code to display
        additional_info: Additional information to include
        
    Returns:
        str: Complete HTML email template
    """
    current_year = datetime.now().year

    
    return f"""\
<html>
  <head>
    <style>
{EMAIL_CSS_STYLES}
    </style>
  </head>
  <body>
    <div class="container">
      <h1>{title}</h1>
      <p>{main_content}</p>
      
      {additional_info}

      <div class="footer">
        <p>Learn more about us at <a href="https://www.bercerita.org/" target="_blank">bercerita.org</a>.</p>
        <p>&copy; {current_year} Bercerita KIRA. All rights reserved.</p>
      </div>
    </div>
  </body>
</html>
"""

def send_admin_verification_email(
    email: str, 
    frontend_route: str, 
    code: str, 
    first_name: str
) -> bool:
    """
    Send verification email to admin for password reset.
    
    Args:
        email: Admin's email address
        frontend_route: Frontend route for verification
        code: Verification code
        first_name: Admin's first name
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    verification_link = f"{settings.FRONTEND_URL}/{frontend_route}/?code={code}&first_name={first_name}"
    
    body_html = _create_email_template(
        title="Bercerita KIRA",
        main_content="Click the button below to reset your password:",
        verification_link=verification_link,
        button_text="Reset Password",
        code=code
    )
    
    return _send_email(
        email=email,
        subject="Bercerita KIRA - Password Reset",
        body_html=body_html
    )


def send_admin_invite_email(
    email: str, 
    frontend_route: str, 
    code: str, 
    user_id: str, 
    school_id: str, 
    first_name: str, 
    last_name: str
) -> bool:
    """
    Send invitation email to new admin.
    
    Args:
        email: New admin's email address
        frontend_route: Frontend route for registration
        code: Verification code
        user_id: User ID
        school_id: School ID
        first_name: Admin's first name
        last_name: Admin's last name
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    verification_link = f"{settings.FRONTEND_URL}/{frontend_route}/?code={code}"
    
    additional_info = """
    <p>If the data is not copied to the page, please use the following information:</p>
    <p>This code will expire in 180 minutes. Please enter it promptly to complete your verification.</p>
    """
    
    body_html = _create_email_template(
        title="Welcome to Bercerita KIRA",
        main_content="Click the button below to register as a Kira admin:",
        verification_link=verification_link,
        button_text="Register with Kira",
        code=code,
        additional_info=additional_info
    )
    
    return _send_email(
        email=email,
        subject="Bercerita KIRA - School Admin Registration",
        body_html=body_html
    )


def send_reset_request_to_admin(
    frontend_route: str, 
    email: str, 
    username: str, 
    school_id: str, 
    first_name: str
) -> bool:
    """
    Send notification to admin about student password reset request.
    
    Args:
        frontend_route: Frontend route for admin login
        email: Admin's email address
        username: Student's username
        school_id: School ID
        first_name: Student's first name
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    verification_link = f"{settings.FRONTEND_URL}/{frontend_route}?email={email}&username={username}"
    
    main_content = f"Student {first_name} with username <strong>{username}</strong> has requested a password reset."
    
    additional_info = """

    """
    
    body_html = _create_email_template(
        title="Bercerita KIRA",
        main_content=main_content,
        verification_link=verification_link,
        button_text="Login",
        additional_info=additional_info
    )
    
    return _send_email(
        email=email,
        subject="Bercerita KIRA - Student Password Reset",
        body_html=body_html
    )

def send_upload_notification(
    email: str, 
    file_name: str
) -> bool:
    """
    Send notification email to new admin.
    
    Args:
        email: 
        file_name: file_name
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    verification_link = f"{settings.FRONTEND_URL}/login"
    
    additional_info = f"""
    <p>Your file {file_name} was uploaded successfully, we will send you another notification when the quiz is ready.</p>
    """
    
    body_html = _create_email_template_without_button(
        title="Status Update",
        main_content="Content Uploaded",
        verification_link=verification_link,
        additional_info=additional_info
    )
    
    return _send_email(
        email=email,
        subject="Bercerita KIRA - Document Upload Successful",
        body_html=body_html
    )

def send_ready_notification(email: str): 
    """
    Send ready notification email to new admin.
    
    Args:
        email: 
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    verification_link = f"{settings.FRONTEND_URL}/login"
    
    additional_info = f""""""
    
    body_html = _create_email_template_without_button(
        title="Status Update",
        main_content="Your quiz is ready for review, please login to review the quiz.",
        verification_link=verification_link,
        additional_info=additional_info
    )
    
    return _send_email(
        email=email,
        subject="Bercerita KIRA - Quiz Ready",
        body_html=body_html
    )