# app/utils/s3_signer.py
import os
from urllib.parse import urlparse
import boto3
from app.config import settings
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-2")
BUCKET = os.getenv("AWS_S3_BUCKET_NAME", "kira-school-content")

_s3 = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_DEFAULT_REGION 
)

def _url_to_key(url_or_key: str) -> str | None:
    if not url_or_key:
        return None
    # If it looks like a key already, return as-is (strip leading '/')
    if "://" not in url_or_key:
        return url_or_key.lstrip("/")
    # Parse full S3 URL and extract the path as key
    u = urlparse(url_or_key)
    # Works for both s3.amazonaws.com and regional s3.<region>.amazonaws.com
    return u.path.lstrip("/")

def presign_get(url_or_key: str, expires_in: int = 300) -> str | None:
    key = _url_to_key(url_or_key)
    if not key:
        return None
    return _s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=expires_in,
    )
