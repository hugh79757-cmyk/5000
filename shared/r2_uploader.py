import os
import logging
import boto3
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"), override=True)

R2_ENDPOINT = os.getenv("R2_ENDPOINT")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET = os.getenv("R2_BUCKET_NAME", "hotissue-images")
R2_PUBLIC_BASE = "https://pub-2f5c7af1c303419a933069212bc25874.r2.dev"


def _get_client():
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        region_name="auto",
    )


def upload_file(local_path, r2_key, content_type="image/webp"):
    """로컬 파일을 R2에 업로드하고 public URL 반환"""
    try:
        s3 = _get_client()
        with open(local_path, "rb") as f:
            s3.put_object(
                Bucket=R2_BUCKET,
                Key=r2_key,
                Body=f.read(),
                ContentType=content_type,
            )
        url = f"{R2_PUBLIC_BASE}/{r2_key}"
        logger.info(f"R2 업로드 완료: {url}")
        return url
    except Exception as e:
        logger.error(f"R2 업로드 실패: {e}")
        return None


def upload_bytes(data, r2_key, content_type="image/png"):
    """바이트 데이터를 R2에 업로드하고 public URL 반환"""
    try:
        s3 = _get_client()
        s3.put_object(
            Bucket=R2_BUCKET,
            Key=r2_key,
            Body=data,
            ContentType=content_type,
        )
        url = f"{R2_PUBLIC_BASE}/{r2_key}"
        logger.info(f"R2 업로드 완료: {url}")
        return url
    except Exception as e:
        logger.error(f"R2 업로드 실패: {e}")
        return None


def file_exists(r2_key):
    """R2에 파일 존재 여부 확인"""
    try:
        s3 = _get_client()
        s3.head_object(Bucket=R2_BUCKET, Key=r2_key)
        return True
    except Exception:
        return False
