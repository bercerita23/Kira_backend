import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from app.config import settings

SENDER = "Bercerita KIRA <dev-team@kira-api.com>"
CONFIGURATION_SET = "ConfigSet"
AWS_REGION = "us-east-2"
SUBJECT = "BERCERITA KIRA - Account Verification Code"
CHARSET = "UTF-8"
                    


def send_admin_verification_email(email: str, 
                            frontend_route: str, 
                            code: str, 
                            first_name: str):
    #verification_link = f"https://main.d3hzyon2wqrdca.amplifyapp.com/signup/?code={code}"
    verification_link = f"{settings.FRONTEND_URL}/{frontend_route}/?code={code}&first_name={first_name}"
    body_html = f"""\
<html>
  <head>
    <style>
      body {{
        font-family: Arial, sans-serif;
        background-color: #f9f9f9;
        color: #333;
        padding: 20px;
      }}
      .container {{
        max-width: 600px;
        margin: 0 auto;
        background-color: #ffffff;
        border-radius: 8px;
        padding: 30px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
      }}
      .code {{
        font-size: 20px;
        font-weight: bold;
        background-color: #f1f1f1;
        padding: 12px 20px;
        border-radius: 6px;
        display: inline-block;
        margin: 20px 0;
        letter-spacing: 2px;
      }}
      .footer {{
        margin-top: 30px;
        font-size: 14px;
        color: #777;
      }}
      a {{
        color: #2a7ae2;
        text-decoration: none;
      }}
    </style>
  </head>
  <body>
    <div class="container">
      <h1>Bercerita KIRA</h1>
      <p>Click the button below to reset your password:</p>
      <a href="{verification_link}" style="display:inline-block;margin-top:16px;padding:12px 24px;background:#2a7ae2;color:#fff;border-radius:6px;text-decoration:none;">Verify Account</a>
      <p>If the link does not work, you can copy and paste the following URL into your browser:</p>
      <p><a href="{verification_link}">{verification_link}</a></p>
      <p>Your verification code is:</p>
      <div class="code">{code}</div>

      <div class="footer">
        <p>Learn more about us at <a href="https://www.bercerita.org/" target="_blank">bercerita.org</a>.</p>
        <p>&copy; {datetime.now().year} Bercerita KIRA. All rights reserved.</p>
      </div>
    </div>
  </body>
</html>
"""
    try:
        client = boto3.client('ses', region_name=AWS_REGION,
                               aws_access_key_id=settings.AWS_ACCESS_KEY_ID, 
                               aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
        response = client.send_email(
            Destination={
                'ToAddresses': [email],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': CHARSET,
                        'Data': body_html,
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': SUBJECT,
                },
            },
            Source=SENDER,
        )
    except ClientError as e:
        print(e.response['Error']['Message'])

def send_admin_invite_email(email: str, frontend_route: str, code: str, user_id: str, school_id: str, first_name: str, last_name: str):
    verification_link = f"{settings.FRONTEND_URL}/{frontend_route}/?email={email}&code={code}&user_id={user_id}&school_id={school_id}&first_name={first_name}&last_name={last_name}"
    body_html = f"""\
<html>
  <head>
    <style>
      body {{
        font-family: Arial, sans-serif;
        background-color: #f9f9f9;
        color: #333;
        padding: 20px;
      }}
      .container {{
        max-width: 600px;
        margin: 0 auto;
        background-color: #ffffff;
        border-radius: 8px;
        padding: 30px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
      }}
      .code {{
        font-size: 20px;
        font-weight: bold;
        background-color: #f1f1f1;
        padding: 12px 20px;
        border-radius: 6px;
        display: inline-block;
        margin: 20px 0;
        letter-spacing: 2px;
      }}
      .footer {{
        margin-top: 30px;
        font-size: 14px;
        color: #777;
      }}
      a {{
        color: #2a7ae2;
        text-decoration: none;
      }}
    </style>
  </head>
  <body>
    <div class="container">
      <h1>Welcome to Bercerita KIRA</h1>
      <p>Click the button below to register as a Kira admin:</p>
      <a href="{verification_link}" style="display:inline-block;margin-top:16px;padding:12px 24px;background:#2a7ae2;color:#fff;border-radius:6px;text-decoration:none;">Regiser with Kira</a>
      <p>If the link does not work, you can copy and paste the following URL into your browser:</p>
      <p><a href="{verification_link}">{verification_link}</a></p>
      <p>If the data is not copied to the page, please use the following information:</p>
      <p>Your verification code is:</p>
      <div class="code">{code}</div>
      <p>Email: {email}</p>
      <p>User ID: {user_id}</p>
      <p>School ID: {school_id}</p>
      <p>First Name: {first_name}</p>
      <p>Last Name: {last_name}</p>
      <p>This code will expire in 10 minutes. Please enter it promptly to complete your verification.</p>

      <div class="footer">
        <p>Learn more about us at <a href="https://www.bercerita.org/" target="_blank">bercerita.org</a>.</p>
        <p>&copy; {datetime.now().year} Bercerita KIRA. All rights reserved.</p>
      </div>
    </div>
  </body>
</html>
"""
    try:
        client = boto3.client('ses', region_name=AWS_REGION,
                               aws_access_key_id=settings.AWS_ACCESS_KEY_ID, 
                               aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
        response = client.send_email(
            Destination={
                'ToAddresses': [email],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': CHARSET,
                        'Data': body_html,
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': SUBJECT,
                },
            },
            Source=SENDER,
        )
    except ClientError as e:
        print(e.response['Error']['Message'])
    
def send_reset_request_to_admin(frontend_route: str, email: str, user_id: str, school_id: str, first_name: str):
  verification_link = f"{settings.FRONTEND_URL}/{frontend_route}"
  body_html = f"""\
<html>
  <head>
    <style>
      body {{
        font-family: Arial, sans-serif;
        background-color: #f9f9f9;
        color: #333;
        padding: 20px;
      }}
      .container {{
        max-width: 600px;
        margin: 0 auto;
        background-color: #ffffff;
        border-radius: 8px;
        padding: 30px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
      }}
      .code {{
        font-size: 20px;
        font-weight: bold;
        background-color: #f1f1f1;
        padding: 12px 20px;
        border-radius: 6px;
        display: inline-block;
        margin: 20px 0;
        letter-spacing: 2px;
      }}
      .footer {{
        margin-top: 30px;
        font-size: 14px;
        color: #777;
      }}
      a {{
        color: #2a7ae2;
        text-decoration: none;
      }}
    </style>
  </head>
  <body>
    <div class="container">
      <h1>Bercerita KIRA</h1>
      <p>Student {first_name} with school ID <strong>{school_id}</strong> and user ID <strong>{user_id}</strong> has requested a password reset.</p>
      <a href="{verification_link}" style="display:inline-block;margin-top:16px;padding:12px 24px;background:#2a7ae2;color:#fff;border-radius:6px;text-decoration:none;">Login</a>
      <p>If the link does not work, you can copy and paste the following URL into your browser:</p>
      <p><a href="{verification_link}">{verification_link}</a></p>
      <p>This code will expire in 10 minutes. Please enter it promptly to complete your verification.</p>
      <div class="footer">
        <p>Learn more about us at <a href="https://www.bercerita.org/" target="_blank">bercerita.org</a>.</p>
        <p>&copy; {datetime.now().year} Bercerita KIRA. All rights reserved.</p>
      </div>
    </div>
  </body>
</html>
"""
  try:
      client = boto3.client('ses', region_name=AWS_REGION,
                             aws_access_key_id=settings.AWS_ACCESS_KEY_ID, 
                             aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
      response = client.send_email(
          Destination={
              'ToAddresses': [email],
          },
          Message={
              'Body': {
                  'Html': {
                      'Charset': CHARSET,
                      'Data': body_html,
                  },
              },
              'Subject': {
                  'Charset': CHARSET,
                  'Data': SUBJECT,
              },
          },
          Source=SENDER,
      )
  except ClientError as e:
      print(e.response['Error']['Message'])