"""RAP 썸네일 생성 + R2 업로드 — v2"""
import os
import hashlib
import logging
import tempfile
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

PALETTE = {
    "부동산":       {"bg1": (20, 45, 80),  "bg2": (40, 75, 130),  "accent": (52, 152, 219),  "badge": (41, 128, 185)},
    "실거래가":     {"bg1": (25, 50, 75),  "bg2": (45, 80, 120),  "accent": (52, 152, 219),  "badge": (52, 152, 219)},
    "청약정보":     {"bg1": (15, 60, 40),  "bg2": (30, 120, 70),  "accent": (46, 204, 113),  "badge": (39, 174, 96)},
    "임대주택":     {"bg1": (50, 25, 70),  "bg2": (100, 50, 130), "accent": (155, 89, 182),  "badge": (142, 68, 173)},
    "부동산세금":   {"bg1": (80, 25, 20),  "bg2": (140, 45, 35),  "accent": (231, 76, 60),   "badge": (192, 57, 43)},
    "전월세":       {"bg1": (15, 65, 40),  "bg2": (25, 110, 65),  "accent": (46, 204, 113),  "badge": (39, 174, 96)},
    "브랜드아파트": {"bg1": (50, 20, 65),  "bg2": (95, 45, 120),  "accent": (165, 105, 200), "badge": (142, 68, 173)},
    "default":      {"bg1": (30, 42, 55),  "bg2": (55, 75, 100),  "accent": (100, 150, 200), "badge": (52, 73, 94)},
}


def _get_font(size):
    font_paths = [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
        "/Library/Fonts/NanumGothicBold.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception as e:
                logger.debug(f"[RAP_THUMB] failed: {e}"); continue
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


def _draw_gradient(draw, width, height, color1, color2):
    """수직 그라데이션"""
    for y in range(height):
        ratio = y / height
        r = int(color1[0] + (color2[0] - color1[0]) * ratio)
        g = int(color1[1] + (color2[1] - color1[1]) * ratio)
        b = int(color1[2] + (color2[2] - color1[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def _draw_rounded_rect(draw, xy, fill, radius=12):
    """둥근 모서리 사각형"""
    x1, y1, x2, y2 = xy
    draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
    draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
    draw.pieslice([x1, y1, x1 + 2 * radius, y1 + 2 * radius], 180, 270, fill=fill)
    draw.pieslice([x2 - 2 * radius, y1, x2, y1 + 2 * radius], 270, 360, fill=fill)
    draw.pieslice([x1, y2 - 2 * radius, x1 + 2 * radius, y2], 90, 180, fill=fill)
    draw.pieslice([x2 - 2 * radius, y2 - 2 * radius, x2, y2], 0, 90, fill=fill)


def generate_rap_thumbnail(title, category="부동산", output_path=None):
    width, height = 600, 400
    colors = PALETTE.get(category, PALETTE["default"])
    img = Image.new("RGB", (width, height), colors["bg1"])
    draw = ImageDraw.Draw(img)

    # 1. 그라데이션 배경
    _draw_gradient(draw, width, height, colors["bg1"], colors["bg2"])

    # 2. 상단 accent 바
    draw.rectangle([(0, 0), (width, 3)], fill=colors["accent"])

    # 3. 좌측 accent 라인
    draw.rectangle([(0, 0), (3, height)], fill=colors["accent"])

    # 4. 카테고리 뱃지 (둥근 사각형)
    badge_font = _get_font(15)
    badge_text = f"  {category}  "
    bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
    badge_w = bbox[2] - bbox[0] + 16
    badge_h = bbox[3] - bbox[1] + 10
    _draw_rounded_rect(draw, (30, 28, 30 + badge_w, 28 + badge_h), fill=colors["badge"], radius=6)
    draw.text((38, 31), badge_text, font=badge_font, fill=(255, 255, 255))

    # 5. 제목 (42px, 최대 4줄, 수직 중앙 정렬)
    title_font = _get_font(24)
    max_text_width = width - 70
    lines = _wrap_text(title, title_font, max_text_width, draw)
    lines = lines[:4]
    line_height = 32
    # 뱃지 하단(110) ~ 구분선 위치(height-120) 사이에서 중앙 정렬
    zone_top = 55
    zone_bottom = height - 65
    total_text_h = len(lines) * line_height
    y = zone_top + (zone_bottom - zone_top - total_text_h) // 2
    for line in lines:
        draw.text((32, y), line, font=title_font, fill=(255, 255, 255))
        y += line_height

    # 6. 구분선 (제목 바로 아래)
    sep_y = y + 8
    draw.line([(32, sep_y), (width - 32, sep_y)], fill=colors["accent"], width=2)

    # 7. 하단 정보
    info_font = _get_font(13)
    date_str = datetime.now().strftime("%Y.%m.%d")
    draw.text((32, height - 35), date_str, font=info_font, fill=(180, 200, 220))

    domain_font = _get_font(12)
    domain = "informationhot.kr"
    dbbox = draw.textbbox((0, 0), domain, font=domain_font)
    dw = dbbox[2] - dbbox[0]
    draw.text((width - 32 - dw, height - 34), domain, font=domain_font, fill=(140, 160, 180))

    # 8. 우측 하단 장식 원
    for i, alpha in enumerate([40, 25, 15]):
        r = 40 + i * 30
        cx, cy = width - 50, height - 40
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        ac = colors["accent"]
        odraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(ac[0], ac[1], ac[2], alpha))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

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
