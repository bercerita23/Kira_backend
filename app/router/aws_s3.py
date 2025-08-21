import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import os
from typing import Optional
from app.config import settings
import re
import logging as logger


class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_DEFAULT_REGION 
        )
        self.bucket_name = settings.AWS_S3_BUCKET_NAME
    
    def upload_file_to_s3(
        self, 
        file_content: bytes, 
        school_id: str, 
        filename: str,
        week_number: int,
        content_type: str = 'application/pdf',
        folder_prefix: str = 'content'
    ) -> Optional[str]:
        """
        Upload file to S3 with organized folder structure
        
        Args:
            file_content: The file content in bytes
            school_id: School identifier for folder organization
            filename: Original filename
            week_number: Week number for additional organization
            
        Returns:
            S3 URL if successful, None if failed
        """
        try:
            # Create the S3 key (path) with folder structure
            # Format: content/{school_id}/week_{week_number}/{filename}
            s3_key = f"{folder_prefix}/{school_id}/{week_number}/{filename}"
            
            # Upload the file
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType=content_type  # Use the parameter instead of hardcoded
            )
            
            # Return the S3 URL
            s3_url = f"https://{self.bucket_name}.s3.amazonaws.com/{s3_key}"
            return s3_url
            
        except NoCredentialsError:
            print("AWS credentials not found")
            return None
        except ClientError as e:
            print(f"Error uploading to S3: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None
        
    def _extract_key_from_url(self, s3_url: str) -> Optional[str]:
        """
        Extract S3 key from S3 URL
        
        Args:
            s3_url: Full S3 URL like https://bucket.s3.amazonaws.com/key/path
            
        Returns:
            S3 key (path) or None if invalid URL
        """
        try:
            # Pattern to match S3 URLs: https://bucket.s3.amazonaws.com/key
            pattern = r'https://[^/]+\.s3\.amazonaws\.com/(.+)'
            match = re.match(pattern, s3_url)
            if match:
                return match.group(1)
            return None
        except Exception as e:
            logger.error(f"Error extracting key from URL {s3_url}: {e}")
            return None
        
    def check_file_exists_by_url(self, s3_url: str) -> bool:
        """
        Check if a file exists in S3 using the full S3 URL
        
        Args:
            s3_url: Full S3 URL from database
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            s3_key = self._extract_key_from_url(s3_url)
            if not s3_key:
                logger.error(f"Invalid S3 URL format: {s3_url}")
                return False
                
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError:
            return False
        
    def delete_file_by_url(self, s3_url: str) -> bool:
        """
        Delete a file from S3 using the full S3 URL (from database)
        
        Args:
            s3_url: Full S3 URL from database
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            s3_key = self._extract_key_from_url(s3_url)
            if not s3_key:
                logger.error(f"Invalid S3 URL format: {s3_url}")
                return False
            
            # Check if file exists before attempting deletion
            if not self.check_file_exists_by_url(s3_url):
                logger.warning(f"File {s3_key} does not exist in S3")
                return False
            
            # Delete the file
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            logger.info(f"Successfully deleted file from S3: {s3_url}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                logger.error(f"Bucket {self.bucket_name} does not exist")
            elif error_code == 'NoSuchKey':
                logger.error(f"File not found in S3: {s3_url}")
            elif error_code == 'AccessDenied':
                logger.error("Access denied for S3 deletion")
            else:
                logger.error(f"AWS ClientError deleting from S3: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting from S3: {e}")
            return False
    
    def get_file_by_url(self, s3_url: str):
        """
        Get file content from S3 into memory using the full S3 URL (no local file created)
        
        Args:
            s3_url: Full S3 URL from database
            
        Returns:
            File content as bytes if successful, None if failed
        """
        try:
            s3_key = self._extract_key_from_url(s3_url)
            if not s3_key:
                logger.error(f"Invalid S3 URL format: {s3_url}")
                return None
            
            # Get the object from S3
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            # Read the file content
            file = response['Body'].read()
            logger.info(f"Successfully retrieved file content from S3: {s3_url}")
            
            return file
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                logger.error(f"Bucket {self.bucket_name} does not exist")
            elif error_code == 'NoSuchKey':
                logger.error(f"File not found in S3: {s3_url}")
            elif error_code == 'AccessDenied':
                logger.error("Access denied for S3 access")
            else:
                logger.error(f"AWS ClientError getting from S3: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting file content from S3: {e}")
            return None
