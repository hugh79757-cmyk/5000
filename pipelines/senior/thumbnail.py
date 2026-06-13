import os
import sys
import textwrap
import logging
import tempfile
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from shared.r2_uploader import upload_file

logger = logging.getLogger(__name__)

WIDTH = 800
HEIGHT = 800
SENIOR_R2_BUCKET = "senior-images"

CATEGORY_COLORS = {
    "의료지원":     [(10, 40, 80), (25, 80, 140)],
    "돌봄서비스":   [(15, 60, 50), (30, 110, 85)],
    "교통복지":     [(60, 40, 10), (120, 80, 20)],
    "생활지원":     [(40, 20, 60), (80, 45, 110)],
    "연금생활지원": [(70, 20, 20), (130, 40, 35)],
    "일자리금융":   [(15, 45, 60), (35, 90, 120)],
    "문화여가":     [(55, 20, 60), (100, 45, 110)],
    "default":      [(20, 35, 55), (45, 70, 100)],
}

BADGE_COLORS = {
    "의료지원":     (50, 120, 200),
    "돌봄서비스":   (45, 160, 120),
    "교통복지":     (190, 130, 50),
    "생활지원":     (130, 80, 180),
    "연금생활지원": (190, 70, 60),
    "일자리금융":   (60, 140, 190),
    "문화여가":     (170, 70, 160),
    "default":      (100, 110, 130),
}

CATEGORY_ICONS = {
    "의료지원":     "🏥",
    "돌봄서비스":   "🤝",
    "교통복지":     "🚌",
    "생활지원":     "🏠",
    "연금생활지원": "💰",
    "일자리금융":   "💼",
    "문화여가":     "🎭",
}


def _make_gradient(width, height, color1, color2):
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    for x in range(width):
        ratio = x / width
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        draw.line([(x, 0), (x, height)], fill=(r, g, b))
    return img


def _get_font(size):
    font_paths = [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
        "/Library/Fonts/NanumGothicBold.ttf",
        "/Library/Fonts/NanumGothic.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception as e:
                logger.debug(f"[SENIOR_THUMB] failed: {e}")
                continue
    return ImageFont.load_default()


def _calc_title_layout(draw, title, max_width, max_lines=3):
    for font_size in [60, 52, 46, 40, 36]:
        font = _get_font(font_size)
        avg_char_w = font_size * 0.85
        chars_per_line = max(int(max_width / avg_char_w), 4)
        wrapped = textwrap.fill(title, width=chars_per_line)
        lines = wrapped.split("\n")
        if len(lines) <= max_lines:
            fits = True
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                if (bbox[2] - bbox[0]) > max_width:
                    fits = False
                    break
            if fits:
                return font, lines, font_size, int(font_size * 1.5)
    font = _get_font(32)
    wrapped = textwrap.fill(title, width=max(int(max_width / (32 * 0.85)), 4))
    lines = wrapped.split("\n")[:max_lines]
    return font, lines, 32, 48


def generate_senior_thumbnail(title, category="default", department="", slug=None, output_path=None):
    """
    썸네일 생성 후 R2 업로드.
    - slug 있으면 → R2 업로드 → URL 반환
    - slug 없으면 → output_path에 로컬 저장 → 경로 반환 (테스트용)
    """
    colors = CATEGORY_COLORS.get(category, CATEGORY_COLORS["default"])
    img = _make_gradient(WIDTH, HEIGHT, colors[0], colors[1])

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for y in range(HEIGHT // 3, HEIGHT):
        alpha = int(80 * ((y - HEIGHT // 3) / (HEIGHT * 2 / 3)))
        overlay_draw.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    padding = 50
    max_text_width = WIDTH - padding * 2

    badge_bottom = padding
    if category and category != "default":
        badge_font = _get_font(20)
        icon = CATEGORY_ICONS.get(category, "📋")
        badge_text = f"{icon} {category}"
        bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
        bw = bbox[2] - bbox[0] + 28
        bh = bbox[3] - bbox[1] + 16
        badge_color = BADGE_COLORS.get(category, BADGE_COLORS["default"])
        draw.rounded_rectangle([padding, padding, padding + bw, padding + bh], radius=10, fill=badge_color)
        draw.text((padding + 14, padding + 6), badge_text, font=badge_font, fill=(255, 255, 255))
        badge_bottom = padding + bh + 30

    title_font, title_lines, font_size, line_height = _calc_title_layout(draw, title, max_text_width)
    total_title_h = len(title_lines) * line_height
    available_h = HEIGHT - badge_bottom - 120
    y_start = badge_bottom + max((available_h - total_title_h) // 2, 10)

    for i, line in enumerate(title_lines):
        y_pos = y_start + i * line_height
        draw.text((padding + 2, y_pos + 2), line, font=title_font, fill=(0, 0, 0, 80))
        draw.text((padding, y_pos), line, font=title_font, fill=(240, 240, 245))

    if department:
        sub_font = _get_font(20)
        sub_y = y_start + len(title_lines) * line_height + 15
        draw.text((padding, sub_y), department, font=sub_font, fill=(160, 175, 200))

    draw.line([(padding, HEIGHT - 60), (WIDTH - padding, HEIGHT - 60)], fill=(255, 255, 255, 30), width=1)
    bottom_font = _get_font(18)
    date_str = datetime.now().strftime("%Y.%m.%d")
    draw.text((padding, HEIGHT - 45), f"시니어복지가이드  |  {date_str}", font=bottom_font, fill=(110, 115, 130))

    # 저장
    if slug:
        tmp = tempfile.NamedTemporaryFile(suffix=".webp", delete=False)
        save_path = tmp.name
        tmp.close()
    else:
        save_path = output_path or "/tmp/senior_thumb.webp"

    os.makedirs(os.path.dirname(save_path) if os.path.dirname(save_path) else ".", exist_ok=True)
    img.save(save_path, "WEBP", quality=85)
    logger.info(f"[SeniorThumb] saved locally: {save_path}")

    # R2 업로드
    if slug:
        r2_key = f"senior/thumbnails/{slug}.webp"
        url = upload_file(save_path, r2_key, content_type="image/webp", bucket=SENIOR_R2_BUCKET)
        try:
            os.unlink(save_path)
        except Exception:
            pass
        if url:
            logger.info(f"[SeniorThumb] R2 완료: {url}")
            return url
        else:
            logger.error("[SeniorThumb] R2 업로드 실패")
            return None

    return save_path


if __name__ == "__main__":
    # 로컬 테스트 (slug 없이)
    generate_senior_thumbnail(
        title="치매 치료관리비 지원, 최대 월 3만원 신청 방법은?",
        category="의료지원",
        department="보건복지부",
        output_path="/tmp/test_senior_thumb1.webp",
    )
    generate_senior_thumbnail(
        title="어르신복지카드 발급, 만 65세 이상 할인 혜택",
        category="교통복지",
        department="행정안전부",
        output_path="/tmp/test_senior_thumb2.webp",
    )
    generate_senior_thumbnail(
        title="기초연금 수급자 확인서 발급 방법과 조건",
        category="연금생활지원",
        department="보건복지부",
        output_path="/tmp/test_senior_thumb3.webp",
    )
    print("테스트 완료: /tmp/test_senior_thumb*.webp")
