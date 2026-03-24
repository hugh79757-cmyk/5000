"""RAP 썸네일 생성 + R2 업로드"""
import os
import hashlib
import logging
import tempfile
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

PALETTE = {
    "부동산": {"bg": (30, 58, 95), "accent": (41, 128, 185)},
    "실거래가": {"bg": (36, 59, 83), "accent": (52, 152, 219)},
    "청약정보": {"bg": (39, 174, 96), "accent": (46, 204, 113)},
    "임대주택": {"bg": (142, 68, 173), "accent": (155, 89, 182)},
    "default": {"bg": (44, 62, 80), "accent": (52, 73, 94)},
}


def _get_font(size):
    font_paths = [
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/NanumGothicBold.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap_text(text, font, max_width, draw):
    lines = []
    current = ""
    for ch in text:
        test = current + ch
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def generate_rap_thumbnail(title, category="부동산", output_path=None):
    width, height = 1200, 630
    colors = PALETTE.get(category, PALETTE["default"])
    img = Image.new("RGB", (width, height), colors["bg"])
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (width, 8)], fill=colors["accent"])

    cat_font = _get_font(28)
    draw.text((60, 50), f"# {category}", font=cat_font, fill=(255, 255, 255, 180))

    title_font = _get_font(52)
    lines = _wrap_text(title, title_font, width - 120, draw)
    y = 140
    for line in lines[:3]:
        draw.text((60, y), line, font=title_font, fill=(255, 255, 255))
        y += 70

    small_font = _get_font(22)
    date_str = datetime.now().strftime("%Y.%m.%d")
    draw.text((60, height - 60), date_str, font=small_font, fill=(200, 200, 200))
    draw.text((width - 250, height - 60), "informationhot.kr", font=small_font, fill=(200, 200, 200))

    if output_path is None:
        output_path = tempfile.mktemp(suffix=".webp")
    img.save(output_path, "WEBP", quality=85)
    logger.info(f"RAP 썸네일 생성: {output_path}")
    return output_path


def upload_thumbnail(title, category="부동산"):
    try:
        from shared.r2_uploader import upload_file
        tmp_path = generate_rap_thumbnail(title, category)
        title_hash = hashlib.md5(title.encode()).hexdigest()[:10]
        r2_key = f"rap-thumbnails/{datetime.now().strftime('%Y%m%d')}-{title_hash}.webp"
        url = upload_file(tmp_path, r2_key, content_type="image/webp")
        os.remove(tmp_path)
        return url
    except Exception as e:
        logger.warning(f"RAP 썸네일 업로드 실패: {e}")
        return None
