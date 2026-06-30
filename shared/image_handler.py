import hashlib
import os
from datetime import datetime
from io import BytesIO

import boto3
from PIL import Image


def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("R2_ENDPOINT"),
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
    )

def process_and_upload(image_data, bucket=None, key_prefix="car-images") -> str:
    if bucket is None:
        bucket = os.getenv("R2_BUCKET", "hotissue-images")

    img = Image.open(BytesIO(image_data))
    img = img.convert("RGB")

    target_w, target_h = 1200, 630
    img_ratio = img.width / img.height
    target_ratio = target_w / target_h

    if img_ratio > target_ratio:
        new_h = img.height
        new_w = int(new_h * target_ratio)
    else:
        new_w = img.width
        new_h = int(new_w / target_ratio)

    left = (img.width - new_w) // 2
    top = (img.height - new_h) // 2
    img = img.crop((left, top, left + new_w, top + new_h))
    img = img.resize((target_w, target_h), Image.LANCZOS)

    output = BytesIO()
    img.save(output, format="WEBP", quality=82)
    output.seek(0)

    now = datetime.now()
    file_hash = hashlib.md5(output.getvalue()).hexdigest()[:8]
    key = f"{key_prefix}/{now.strftime('%Y/%m/%d')}/{file_hash}.webp"

    client = get_r2_client()
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=output.getvalue(),
        ContentType="image/webp",
    )

    return f"{os.getenv('R2_PUBLIC_URL')}/{key}"
