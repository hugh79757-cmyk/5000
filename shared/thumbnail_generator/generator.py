"""
Centralized editorial thumbnail generator — Playwright + HTML/CSS → WebP → R2.

Originally derived from informationhot-hugo/scripts/generate_thumbnail.py.
Now the single source of thumbnails for all 5000-managed blogs.

Usage:
    from shared.thumbnail_generator import generate_thumbnail

    url = generate_thumbnail(
        site_id="senior",
        slug="2026-치매-치료관리비-지원",
        title="치매 치료관리비 지원, 최대 월 3만원 신청 방법은?",
        category="의료지원",
    )
"""

import hashlib
import logging
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from shared.thumbnail_generator.colors import (
    get_blog_palette,
    get_accent_for_category,
)

logger = logging.getLogger(__name__)

# Path setup — template directory relative to this file
TEMPLATE_DIR = Path(__file__).parent / "templates"

# Constants
RENDER_WIDTH = 600
RENDER_HEIGHT = 600
OUTPUT_WEBP_QUALITY = 80
MAX_WEBP_SIZE = 50 * 1024  # 50KB target


# ── Title splitting ─────────────────────────────────────────────────────────

def split_title(title: str) -> tuple[str, str]:
    """
    Split a title into two lines for the dynamic typography template.
    Returns (line1, line2) — line2 may be empty.
    """
    title = title.strip().strip('"').strip("'")

    if len(title) < 15:
        return title, ""

    # Try natural break points
    separators = [" — ", " – ", " / ", " : ", " :", " - ", "(", "? "]
    for sep in separators:
        if sep in title:
            idx = title.index(sep)
            if idx < 25:
                part1 = title[:idx].strip()
                part2 = title[idx + len(sep):].strip().rstrip(")")
                if part1 and part2:
                    return part1, part2

    # Word-boundary split near midpoint
    space_positions = [i for i, ch in enumerate(title) if ch == " "]
    if len(space_positions) >= 1 and len(title) >= 15:
        mid = len(title) / 2
        best_pos = None
        best_score = float("inf")
        for pos in space_positions:
            if pos < 3 or pos > len(title) - 3:
                continue
            if len(title) - pos - 1 < 3:
                continue
            score = abs(pos - mid) - (0.8 * (pos - mid) if pos > mid else 0)
            if score < best_score:
                best_score = score
                best_pos = pos
        if best_pos is not None:
            part1 = title[:best_pos].strip()
            part2 = title[best_pos:].strip()
            if part1 and part2:
                return part1, part2

    if len(title) > 22:
        return title[:22].rstrip(), title[22:].strip()

    return title, ""


def _calc_font_sizes(title_line1: str, title_line2: str) -> dict:
    """Determine optimal font sizes based on line lengths."""
    len1 = len(title_line1)
    if len1 <= 6:
        title1_size = 64
    elif len1 <= 10:
        title1_size = 56
    elif len1 <= 15:
        title1_size = 48
    else:
        title1_size = 40

    len2 = len(title_line2)
    if not title_line2:
        title2_size = 0
    elif len2 <= 10:
        title2_size = 44
    elif len2 <= 18:
        title2_size = 38
    elif len2 <= 28:
        title2_size = 32
    else:
        title2_size = 26

    return {"title1_size": title1_size, "title2_size": title2_size}


# ── Sandboxed Playwright import ─────────────────────────────────────────────

def _import_playwright():
    """
    Import Playwright safely. Returns (sync_playwright, None) or (None, error_msg).
    This avoids ImportError at module level when Playwright isn't installed.
    """
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright, None
    except ImportError:
        return None, "playwright not installed (pip install playwright && playwright install chromium)"
    except Exception as e:
        return None, f"playwright import error: {e}"


# ── Chromium self-heal (cache purge recovery) ────────────────────────────────
# 사용자가 ~/Library/Caches/ms-playwright를 주기적으로 삭제해 chromium 바이너리만
# 유실되면 "Executable doesn't exist" 크래시로 파이프라인이 며칠간 중단된다.
# launch 직전 부재를 감지해 자동 설치 후 계속 진행한다 (260913-g12).

_PW_INSTALL_LOCK = "/tmp/5000_pw_chromium_install.lock"
_PW_INSTALL_RETRY_SECONDS = 6 * 3600  # 설치 실패(오프라인 등) 후 6시간 재시도 쿨다운
_PW_INSTALL_WAIT_SECONDS = 240  # 다른 프로세스가 설치 중일 때 executable 출현 폴링 상한
_PW_INSTALL_TIMEOUT = 600  # playwright install chromium 다운로드 timeout (280MB)


def _chromium_attempt_marker() -> Path:
    """설치 시도 마커 경로 — repo_root/data/ 기준 (CWD 무관)."""
    return Path(__file__).resolve().parents[2] / "data" / ".pw_chromium_install_attempt"


def _install_chromium_locked() -> None:
    """
    chromium 바이너리가 없을 때 1회 자동 설치한다.

    - /tmp lock(non-blocking)으로 dispatcher 동시 실행 시 중복 280MB 다운로드 방지
    - 잠금 획득 실패(다른 프로세스 설치 중) → executable 출현을 5s 간격 폴링
    - 마커 쿨다운(6h)으로 오프라인 재시도 루프 방지
    - 실패는 조용히 통과하지 않고 RuntimeError raise
    """
    import fcntl as _fl
    import subprocess
    import time as _time

    from playwright.sync_api import sync_playwright as _spw

    marker = _chromium_attempt_marker()

    # 마커 쿨다운 — 최근 실패(성공 여부와 무관하게 마지막 시도) 후 6h 내 재시도 금지.
    # 마커에는 성공 시각도 기록하나, 성공 시 executable이 존재하므로 이 경로 자체에
    # 진입하지 않는다. 여기 도달했다는 것은 마지막 시도가 실패했다는 뜻이다.
    if marker.exists():
        try:
            last = _time.time() - marker.stat().st_mtime
            if last < _PW_INSTALL_RETRY_SECONDS:
                raise RuntimeError(
                    f"[ThumbGen] playwright chromium install skipped — "
                    f"last attempt {_PW_INSTALL_RETRY_SECONDS // 3600}h cooldown "
                    f"(marker: {marker}, age: {int(last)}s)"
                )
        except OSError:
            pass  # 마커 stat 실패는 설치 시도를 계속 진행

    lock_file = open(_PW_INSTALL_LOCK, "w")
    try:
        try:
            _fl.flock(lock_file, _fl.LOCK_EX | _fl.LOCK_NB)
        except BlockingIOError:
            # 다른 프로세스가 이미 설치 중 — 출현 폴링
            deadline = _time.time() + _PW_INSTALL_WAIT_SECONDS
            with _spw() as pw:
                exe = pw.chromium.executable_path
            while _time.time() < deadline:
                if os.path.exists(exe):
                    logger.info("[ThumbGen] Chromium installed by concurrent process — continuing")
                    return
                _time.sleep(5)
            raise RuntimeError(
                f"[ThumbGen] timed out waiting for concurrent chromium install "
                f"({_PW_INSTALL_WAIT_SECONDS}s): {exe}"
            )

        # 잠금 획득 — 다른 프로세스가 방금 완료했을 수 있으니 재확인
        with _spw() as pw:
            exe = pw.chromium.executable_path
        if os.path.exists(exe):
            logger.info("[ThumbGen] Chromium appeared while waiting for lock — skipping install")
            return

        logger.info(
            "[ThumbGen] Chromium executable missing — attempting self-install "
            "(this can take a few minutes)"
        )
        proc = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            timeout=_PW_INSTALL_TIMEOUT,
            capture_output=True,
        )
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()  # 성공/실패 모두 시도 시각 기록

        if proc.returncode != 0:
            logger.error(
                "[ThumbGen] playwright install chromium FAILED (rc=%d): %s",
                proc.returncode,
                (proc.stderr or b"").decode(errors="replace")[-500:],
            )
            raise RuntimeError(
                f"[ThumbGen] playwright install chromium failed (rc={proc.returncode}): "
                f"{(proc.stderr or b'').decode(errors='replace')[-500:]}"
            )
        if not os.path.exists(exe):
            raise RuntimeError(
                f"playwright chromium executable missing after install attempt: {exe}"
            )
        logger.info("[ThumbGen] Chromium self-install complete")
    finally:
        # 잠금 획득 성공 여부와 무관게 fd는 닫는다 (close가 flock 해제)
        try:
            lock_file.close()
        except OSError:
            pass


def _ensure_chromium(pw) -> None:
    """
    chromium 실행 파일이 존재하는지 확인하고, 없으면 자동 설치한다.

    정상 상태(이미 설치됨)에서는 os.path.exists 1회 체크만 추가된다.
    """
    if os.path.exists(pw.chromium.executable_path):
        return
    _install_chromium_locked()


# ── Public API ──────────────────────────────────────────────────────────────

def generate_thumbnail(
    site_id: str,
    slug: str,
    title: str,
    category: str = "",
    output_path: str | None = None,
    upload: bool = True,
    template_name: str = "default.html",
    _page=None,
    extra_context: dict | None = None,
) -> str:
    """
    Generate a blog thumbnail image and upload to R2.

    Args:
        site_id: Blog identifier (e.g., "senior", "stock", "kuta", "techpawz")
        slug: Post slug (used for R2 key)
        title: Post title
        category: Post category (for badge + accent color)
        output_path: Local output path (skip R2 upload if given + upload=False)
        upload: Whether to upload to R2
        template_name: HTML template file name in templates/
        _page: Internal — shared Playwright page for batch processing
        extra_context: Additional template variables

    Returns:
        Public R2 URL (if upload=True) or local file path (if upload=False)
    """
    # Get blog-specific colors
    palette = get_blog_palette(site_id)
    accent = get_accent_for_category(site_id, category)
    badge_bg = palette.get("badge_bg", "rgba(255,255,255,0.2)")
    site_bar = palette.get("site_bar", "")

    # Split title
    title_line1, title_line2 = split_title(title)
    font_sizes = _calc_font_sizes(title_line1, title_line2)

    # Render template
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    try:
        template = env.get_template(template_name)
    except Exception:
        logger.warning(f"[ThumbGen] Template '{template_name}' not found, falling back to default.html")
        template = env.get_template("default.html")

    ctx = dict(
        accent=accent,
        title_line1=title_line1,
        title_line2=title_line2,
        title1_size=font_sizes["title1_size"],
        title1_size_single=font_sizes["title1_size"],
        title2_size=font_sizes["title2_size"],
        category=category or "",
        badge_bg=badge_bg,
        site_bar=site_bar,
    )
    if extra_context:
        ctx.update(extra_context)
    html_content = template.render(ctx)

    # Write temporary HTML file
    tmp_html = _write_temp_html(slug, html_content, output_path)

    try:
        # Render with Playwright
        if _page is not None:
            _page.goto(f"file://{tmp_html}", wait_until="networkidle")
            _page.wait_for_timeout(1500)
            if output_path and not output_path.endswith(".webp"):
                png_path = output_path
            else:
                png_path = tmp_html.replace(".html", ".png")
            _page.screenshot(path=png_path, full_page=False)
        else:
            sync_playwright, err = _import_playwright()
            if err:
                logger.error(f"[ThumbGen] {err}")
                raise RuntimeError(err)

            with sync_playwright() as pw:
                _ensure_chromium(pw)
                browser = pw.chromium.launch()
                page = browser.new_page(
                    viewport={"width": RENDER_WIDTH, "height": RENDER_HEIGHT},
                    device_scale_factor=2,
                )
                page.goto(f"file://{tmp_html}", wait_until="networkidle")
                page.wait_for_timeout(1500)  # Font load

                if output_path and not output_path.endswith(".webp"):
                    png_path = output_path
                else:
                    png_path = tmp_html.replace(".html", ".png")

                page.screenshot(path=png_path, full_page=False)
                browser.close()

        # Convert PNG → WebP
        from PIL import Image

        img = Image.open(png_path)
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg
        if img.width > RENDER_WIDTH or img.height > RENDER_HEIGHT:
            img.thumbnail((RENDER_WIDTH, RENDER_HEIGHT), Image.LANCZOS)

        if output_path and output_path.endswith(".webp"):
            webp_path = output_path
        else:
            webp_path = png_path.replace(".png", ".webp")
        img.save(webp_path, "WEBP", quality=OUTPUT_WEBP_QUALITY, method=4)

        # Size optimization
        size = os.path.getsize(webp_path)
        quality = OUTPUT_WEBP_QUALITY
        while size > MAX_WEBP_SIZE and quality > 30:
            quality -= 10
            img.save(webp_path, "WEBP", quality=quality, method=4)
            size = os.path.getsize(webp_path)

        # Clean up PNG
        if os.path.exists(png_path) and png_path != output_path:
            os.remove(png_path)

        if upload:
            return _upload_to_r2(site_id, slug, webp_path, tmp_html)
        else:
            webp_size = os.path.getsize(webp_path)
            logger.info(f"[ThumbGen] Generated: {webp_path} ({webp_size // 1024}KB)")
            return webp_path

    finally:
        _cleanup_temp(tmp_html, output_path)


def _write_temp_html(slug: str, html_content: str, output_path: str | None) -> str:
    """Write HTML content to a temporary file for Playwright to render."""
    if output_path:
        tmp_dir = Path(output_path).parent
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_html = str(tmp_dir / f"_{slug}.html")
    else:
        tmp_fd, tmp_html = tempfile.mkstemp(suffix=".html", prefix="thumb_")
        os.close(tmp_fd)

    with open(tmp_html, "w") as f:
        f.write(html_content)
    return tmp_html


def _upload_to_r2(site_id: str, slug: str, webp_path: str, tmp_html: str) -> str:
    """Upload the generated WebP to R2 and return the public URL."""
    from shared.r2_uploader import upload_file

    # Sanitize slug for R2 key (NFC-normalize first so Jamo -> composed Hangul)
    nfc_slug = unicodedata.normalize("NFC", slug)
    safe_slug = re.sub(r"[^a-zA-Z0-9가-힣\-_]", "", nfc_slug).strip("-")[:80]
    r2_key = f"thumbnails/{site_id}/{safe_slug}.webp"
    public_url = upload_file(str(webp_path), r2_key, content_type="image/webp")

    # Clean up temp files
    if os.path.exists(webp_path):
        os.remove(webp_path)
    if os.path.exists(tmp_html):
        os.remove(tmp_html)

    size = os.path.getsize(webp_path) if os.path.exists(webp_path) else 0
    logger.info(f"[ThumbGen] Uploaded {site_id}/{safe_slug}.webp ({size // 1024}KB) → {public_url}")
    return public_url


def _cleanup_temp(tmp_html: str, output_path: str | None):
    """Clean up temp HTML if it wasn't requested as output."""
    if tmp_html and not output_path and os.path.exists(tmp_html):
        try:
            os.remove(tmp_html)
        except Exception:
            pass


def generate_image_thumbnail(
    site_id: str,
    slug: str,
    title: str,
    category: str = "",
    output_path: str | None = None,
    upload: bool = True,
    _page=None,
) -> str:
    """
    Generate a thumbnail with an Unsplash photo as background image.
    Falls back to standard text-only generate_thumbnail() on any failure.

    The function searches Unsplash for a photo matching the category,
    resizes it, base64-encodes it as a data URI, and passes it to the
    image.html template.
    """
    background_data_uri = None
    try:
        from pipelines.etap.image_fetcher import _search_unsplash
        import base64
        import io
        import random

        import httpx
        from PIL import Image

        photos = _search_unsplash(category or site_id, per_page=5)
        if photos:
            photo = random.choice(photos)
            resp = httpx.get(photo["url"], timeout=15)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content))
            # Center-crop to 600x600 to keep data URI small
            size = min(img.size)
            left = (img.width - size) // 2
            top = (img.height - size) // 2
            img = img.crop((left, top, left + size, top + size)).resize((600, 600), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, "WEBP", quality=75)
            b64 = base64.b64encode(buf.getvalue()).decode()
            background_data_uri = f"data:image/webp;base64,{b64}"
    except Exception as e:
        logger.warning(f"[ThumbGen] Unsplash search/process failed ({e}), falling back to text")

    if background_data_uri:
        return generate_thumbnail(
            site_id=site_id, slug=slug, title=title, category=category,
            output_path=output_path, upload=upload, _page=_page,
            template_name="image.html",
            extra_context={"background_data_uri": background_data_uri},
        )

    # Fallback
    return generate_thumbnail(
        site_id=site_id, slug=slug, title=title, category=category,
        output_path=output_path, upload=upload, _page=_page,
    )


def generate_batch(
    site_id: str,
    posts: list[dict],
    template_name: str = "default.html",
    progress_callback=None,
) -> list[dict]:
    """
    Generate thumbnails for multiple posts in a single browser session.
    Much faster than individual calls when processing hundreds of posts.

    Args:
        site_id: Blog identifier
        posts: List of dicts with keys: slug, title, category
        template_name: HTML template file name
        progress_callback: Optional fn(slug, success, result) called after each post

    Returns:
        List of dicts with keys: slug, url (R2), success (bool), error (str)
    """
    sync_playwright, err = _import_playwright()
    if err:
        logger.error(f"[ThumbGen] Batch failed: {err}")
        return [{"slug": p.get("slug", "?"), "url": None, "success": False, "error": err} for p in posts]

    results = []
    with sync_playwright() as pw:
        _ensure_chromium(pw)
        browser = pw.chromium.launch()
        page = browser.new_page(
            viewport={"width": RENDER_WIDTH, "height": RENDER_HEIGHT},
            device_scale_factor=2,
        )

        for idx, post in enumerate(posts):
            slug = post.get("slug", "")
            title = post.get("title", "")
            category = post.get("category", "")

            # Fresh page every 50 posts to prevent chromium memory buildup
            if idx > 0 and idx % 50 == 0:
                try:
                    page.close()
                except Exception:
                    pass
                page = browser.new_page(
                    viewport={"width": RENDER_WIDTH, "height": RENDER_HEIGHT},
                    device_scale_factor=2,
                )

            try:
                url = generate_thumbnail(
                    site_id=site_id,
                    slug=slug,
                    title=title,
                    category=category,
                    upload=True,
                    template_name=template_name,
                    _page=page,
                )
                results.append({"slug": slug, "url": url, "success": True, "error": None})
                if progress_callback:
                    progress_callback(slug, True, url)
            except Exception as e:
                logger.error(f"[ThumbGen] Batch failed for {slug}: {e}")
                results.append({"slug": slug, "url": None, "success": False, "error": str(e)})
                if progress_callback:
                    progress_callback(slug, False, str(e))

            if (idx + 1) % 50 == 0:
                logger.info(f"[ThumbGen] Batch progress: {idx + 1}/{len(posts)}")

        browser.close()

    return results
