import os
import logging
import sys
import boto3
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"), override=True)

R2_ENDPOINT = os.getenv("R2_ENDPOINT")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_DEFAULT = os.getenv("R2_BUCKET_NAME", "hotissue-images")

BUCKET_PUBLIC_URLS = {
    "hotissue-images": "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev",
    "senior-images":   os.getenv("SENIOR_R2_PUBLIC_URL", "https://pub-3f702c9170934a72bc62a5436c406aa6.r2.dev"),
}


def _get_client():
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        region_name="auto",
    )


def _public_url(bucket, r2_key):
    base = BUCKET_PUBLIC_URLS.get(bucket, f"https://pub-unknown.r2.dev")
    return f"{base}/{r2_key}"


def upload_file(local_path, r2_key, content_type="image/webp", bucket=None):
    """로컬 파일을 R2에 업로드하고 public URL 반환"""
    bucket = bucket or R2_BUCKET_DEFAULT
    try:
        s3 = _get_client()
        with open(local_path, "rb") as f:
            s3.put_object(
                Bucket=bucket,
                Key=r2_key,
                Body=f.read(),
                ContentType=content_type,
            )
        url = _public_url(bucket, r2_key)
        logger.info(f"R2 업로드 완료: {url}")
        return url
    except Exception as e:
        logger.error(f"R2 업로드 실패: {e}")
        return None


def upload_bytes(data, r2_key, content_type="image/png", bucket=None):
    """바이트 데이터를 R2에 업로드하고 public URL 반환"""
    bucket = bucket or R2_BUCKET_DEFAULT
    try:
        s3 = _get_client()
        s3.put_object(
            Bucket=bucket,
            Key=r2_key,
            Body=data,
            ContentType=content_type,
        )
        url = _public_url(bucket, r2_key)
        logger.info(f"R2 업로드 완료: {url}")
        return url
    except Exception as e:
        logger.error(f"R2 업로드 실패: {e}")
        return None


def file_exists(r2_key, bucket=None):
    """R2에 파일 존재 여부 확인"""
    bucket = bucket or R2_BUCKET_DEFAULT
    try:
        s3 = _get_client()
        s3.head_object(Bucket=bucket, Key=r2_key)
        return True
    except Exception:
        return False
