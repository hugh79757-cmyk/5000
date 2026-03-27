import os
import io
import textwrap
import logging
import requests
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

logger = logging.getLogger(__name__)

WIDTH = 800
HEIGHT = 800

CATEGORY_COLORS = {
    "공시분석": [(15, 22, 45), (30, 60, 90)],
    "실적분석": [(10, 30, 25), (25, 65, 55)],
    "배당분석": [(40, 15, 15), (75, 30, 25)],
    "IPO분석":  [(25, 12, 40), (55, 30, 75)],
    "ETF분석":  [(12, 25, 40), (30, 55, 80)],
    "시장분석": [(20, 20, 25), (45, 45, 55)],
    "default":  [(18, 18, 30), (40, 40, 60)],
}

BADGE_COLORS = {
    "공시분석": (65, 120, 190),
    "실적분석": (55, 170, 130),
    "배당분석": (200, 120, 80),
    "IPO분석":  (150, 100, 200),
    "ETF분석":  (70, 150, 200),
    "시장분석": (140, 145, 160),
    "default":  (120, 125, 145),
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
                logger.debug(f"[STOCK_THUMB] failed: {e}"); continue
    return ImageFont.load_default()


def _fetch_logo(stock_code):
    if not stock_code:
        return None
    for url_pattern in [
        f"https://static.toss.im/png-icons/securities/icn-sec-fill-{stock_code}.png",
        f"https://file.alphasquare.co.kr/media/images/stock_logo/kr/{stock_code}.png",
    ]:
        try:
            r = requests.get(url_pattern, timeout=5)
            if r.status_code == 200 and len(r.content) > 500:
                logo = Image.open(io.BytesIO(r.content)).convert("RGBA")
                return logo
        except Exception as e:
            logger.debug(f"[STOCK_THUMB] failed: {e}"); continue
    return None


def _calc_title_layout(draw, title, max_width, max_lines=3):
    for font_size in [64, 56, 50, 44, 38]:
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
    font = _get_font(34)
    wrapped = textwrap.fill(title, width=max(int(max_width / (34 * 0.85)), 4))
    lines = wrapped.split("\n")[:max_lines]
    return font, lines, 34, 50


def generate_stock_thumbnail(title, category="default", stock_code="", corp_name="", output_path="thumbnail.webp"):
    colors = CATEGORY_COLORS.get(category, CATEGORY_COLORS["default"])
    img = _make_gradient(WIDTH, HEIGHT, colors[0], colors[1])

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for y in range(HEIGHT // 3, HEIGHT):
        alpha = int(80 * ((y - HEIGHT // 3) / (HEIGHT * 2 / 3)))
        overlay_draw.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    logo = _fetch_logo(stock_code)

    draw = ImageDraw.Draw(img)
    padding = 50

    # 로고는 우상단 고정, 텍스트는 전체 폭 사용
    if logo:
        logo_size = 140
        logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
        logo_x = WIDTH - padding - logo_size
        logo_y = padding
        img.paste(Image.new("RGB", (logo_size + 16, logo_size + 16), (255, 255, 255)), (logo_x - 8, logo_y - 8))
        img.paste(logo, (logo_x, logo_y), logo)
        draw = ImageDraw.Draw(img)

    max_text_width = WIDTH - padding * 2

    badge_bottom = padding
    if category and category != "default":
        badge_font = _get_font(20)
        bbox = draw.textbbox((0, 0), category, font=badge_font)
        bw = bbox[2] - bbox[0] + 24
        bh = bbox[3] - bbox[1] + 14
        badge_color = BADGE_COLORS.get(category, BADGE_COLORS["default"])
        draw.rounded_rectangle([padding, padding, padding + bw, padding + bh], radius=8, fill=badge_color)
        draw.text((padding + 12, padding + 5), category, font=badge_font, fill=(255, 255, 255))
        badge_bottom = padding + bh + 25

    title_font, title_lines, font_size, line_height = _calc_title_layout(draw, title, max_text_width)
    total_title_h = len(title_lines) * line_height
    available_h = HEIGHT - badge_bottom - 100
    y_start = badge_bottom + max((available_h - total_title_h) // 2, 10)

    for i, line in enumerate(title_lines):
        y_pos = y_start + i * line_height
        draw.text((padding + 2, y_pos + 2), line, font=title_font, fill=(0, 0, 0, 80))
        draw.text((padding, y_pos), line, font=title_font, fill=(240, 240, 245))

    if corp_name and stock_code:
        sub_text = f"{corp_name} ({stock_code})"
        sub_font = _get_font(22)
        sub_y = y_start + len(title_lines) * line_height + 10
        draw.text((padding, sub_y), sub_text, font=sub_font, fill=(160, 175, 200))

    draw.line([(padding, HEIGHT - 60), (WIDTH - padding, HEIGHT - 60)], fill=(255, 255, 255, 30), width=1)
    bottom_font = _get_font(18)
    date_str = datetime.now().strftime("%Y.%m.%d")
    draw.text((padding, HEIGHT - 45), f"캔들트렌드  |  {date_str}", font=bottom_font, fill=(110, 115, 130))

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    img.save(output_path, "WEBP", quality=85)
    logger.info(f"[StockThumb] saved: {output_path}")
    return output_path


if __name__ == "__main__":
    generate_stock_thumbnail(
        title="삼성전자 실적 발표, 영업이익 40% 급감 바닥은 어디일까",
        category="실적분석",
        stock_code="005930",
        corp_name="삼성전자",
        output_path="/tmp/test_stock_thumb1.webp",
    )
    generate_stock_thumbnail(
        title="2026년 고배당주 TOP 10 연 8% 수익 가능한 종목은",
        category="배당분석",
        output_path="/tmp/test_stock_thumb2.webp",
    )
    generate_stock_thumbnail(
        title="한국정보인증 사업보고서 분석 투자 포인트",
        category="공시분석",
        stock_code="053300",
        corp_name="한국정보인증",
        output_path="/tmp/test_stock_thumb3.webp",
    )
    print("테스트 썸네일 생성 완료: /tmp/test_stock_thumb*.webp")
