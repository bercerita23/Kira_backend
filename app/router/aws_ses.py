import boto3

def send_verification_email(email: str, code: str):
    client = boto3.client("ses", region_name="us-east-2")  
    client.send_email(
        Source="khakho.morad@gmail.com",
        Destination={"ToAddresses": [email]},
        Message={
            "Subject": {"Data": "Your Bercerita KIRA Verification Code"},
            "Body": {
                "Text": {"Data": f"Your code is: {code}\nIt expires in 10 minutes."}
            },
        },
    )
