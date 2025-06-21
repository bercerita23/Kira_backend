import boto3
from botocore.exceptions import ClientError
from datetime import datetime

SENDER = "Bercerita KIRA <dev-team@kira-api.com>"
CONFIGURATION_SET = "ConfigSet"
AWS_REGION = "us-east-2"
SUBJECT = "BERCERITA KIRA - Account Verification Code"
CHARSET = "UTF-8"

def send_verification_email(email: str, code: str):
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
        font-size: 24px;
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
      <p>Your verification code is:</p>
      <div class="code">{code}</div>
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
        client = boto3.client('ses', region_name=AWS_REGION)
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