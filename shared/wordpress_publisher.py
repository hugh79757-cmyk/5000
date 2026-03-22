"""워드프레스 발행 - blog_manager 연동 + 블록 편집기 지원 (v2.10.14)"""

import logging
import os
import re
import base64
import requests
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)


# content_type → 워드프레스 카테고리 slug 매핑
CATEGORY_MAP = {
    'restaurant': 'restaurant',
    'cafe': 'restaurant',
    'recipe': 'recipe',
    'misc_person': 'people',
    'person': 'people',
    'misc_place': 'travel',
    'place': 'travel',
    'misc_event': 'lifestyle',
    'misc_tip': 'lifestyle',
    'misc_product': 'lifestyle',
    'misc_other': 'lifestyle',
    'general': 'lifestyle',
    'misc': 'lifestyle',
}


class WordPressPublisher:
    """워드프레스 REST API 발행기"""
    
    def __init__(self, blog_id: str = None):
        """
        Args:
            blog_id: blogs.yaml의 블로그 ID (예: 'wordpress_biz')
                     None이면 기본 settings.py 환경변수 사용
        """
        if blog_id:
            # blogs.yaml에서 설정 로드
            try:
                from config.blog_manager import get_blog_by_id, get_blog_credentials
                blog = get_blog_by_id(blog_id)
                if blog:
                    creds = get_blog_credentials(blog)
                    self.url = creds.get('url', '').rstrip('/')
                    self.username = creds.get('username', '')
                    self.password = creds.get('password', '')
                    logger.info(f"[WordPress] blogs.yaml에서 로드: {blog_id} -> {self.url}")
                else:
                    logger.warning(f"[WordPress] 블로그 ID 없음: {blog_id}, 기본값 사용")
                    self._load_from_settings()
            except Exception as e:
                logger.warning(f"[WordPress] blog_manager 로드 실패: {e}, 기본값 사용")
                self._load_from_settings()
        else:
            self._load_from_settings()
        
        self.api_url = f"{self.url}/wp-json/wp/v2" if self.url else ""
    
    def _load_from_settings(self):
        """settings.py에서 기본 환경변수 로드"""
        from config import settings
        self.url = settings.WORDPRESS_URL.rstrip('/') if settings.WORDPRESS_URL else ''
        self.username = settings.WORDPRESS_USERNAME
        self.password = settings.WORDPRESS_APP_PASSWORD
    
    def is_configured(self) -> bool:
        """설정 여부 확인"""
        return bool(self.url and self.username and self.password)
    
    def connect(self) -> bool:
        """연결 테스트"""
        if not self.is_configured():
            logger.error("워드프레스 설정 미완료")
            return False
        
        try:
            response = requests.get(
                f"{self.api_url}/posts",
                auth=(self.username, self.password),
                params={"per_page": 1},
                timeout=10
            )
            if response.status_code == 200:
                logger.info(f"워드프레스 연결 성공: {self.url}")
                return True
            else:
                logger.error(f"워드프레스 연결 실패: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"워드프레스 연결 오류: {e}")
            return False
    
    def _convert_to_blocks(self, html: str) -> str:
        """HTML을 구텐베르크 블록으로 변환 (v2.5.1)"""
        if '<!-- wp:' in html:
            return html

        import re as _re

        # 1. meta 태그 제거
        html = _re.sub(r'<meta[^>]*>', '', html)

        # 2. h2/h3에 tv-show 클래스 추가 (기존 style은 제거)
        html = _re.sub(
            r'<h2(?:\s[^>]*)?>',
            '<h2 style="font-size:1.6em;font-weight:bold;margin:30px 0 15px 0;padding-bottom:8px;border-bottom:2px solid #2196F3;color:#1a1a1a;">',
            html
        )
        html = _re.sub(
            r'<h3(?:\s[^>]*)?>',
            '<h3 style="font-size:1.3em;font-weight:bold;margin:25px 0 12px 0;color:#333;">',
            html
        )

        # 3. 블록 변환
        raw = html.strip()
        blocks = []
        pos = 0

        while pos < len(raw):
            # 공백 스킵
            ws = _re.match(r'\s+', raw[pos:])
            if ws:
                pos += ws.end()
                continue
            if pos >= len(raw):
                break

            # <h2>~</h6>
            hm = _re.match(r'(<h([2-6])\b[^>]*>.*?</h\2>)', raw[pos:], _re.DOTALL)
            if hm:
                level = hm.group(2)
                tag = hm.group(0)
                # class 속성을 구텐베르크 className으로 변환
                cls_m = _re.search(r'class="([^"]*)"', tag)
                cls_attr = ''
                if cls_m:
                    cls_attr = ',"className":"' + cls_m.group(1) + '"'
                blocks.append('<!-- wp:heading {"level":' + level + cls_attr + '} -->\n' + tag + '\n<!-- /wp:heading -->')
                pos += hm.end()
                continue

            # <p>...</p>
            pm = _re.match(r'(<p\b[^>]*>.*?</p>)', raw[pos:], _re.DOTALL)
            if pm:
                blocks.append('<!-- wp:paragraph -->\n' + pm.group(0) + '\n<!-- /wp:paragraph -->')
                pos += pm.end()
                continue

            # <ul>...</ul>
            um = _re.match(r'(<ul\b[^>]*>.*?</ul>)', raw[pos:], _re.DOTALL)
            if um:
                blocks.append('<!-- wp:list -->\n' + um.group(0) + '\n<!-- /wp:list -->')
                pos += um.end()
                continue

            # <ol>...</ol>
            om = _re.match(r'(<ol\b[^>]*>.*?</ol>)', raw[pos:], _re.DOTALL)
            if om:
                blocks.append('<!-- wp:list {"ordered":true} -->\n' + om.group(0) + '\n<!-- /wp:list -->')
                pos += om.end()
                continue

            # <table>...</table>
            tm = _re.match(r'(<table[^>]*>.*?</table>)', raw[pos:], _re.DOTALL)
            if tm:
                blocks.append('<!-- wp:html -->\n' + tm.group(0) + '\n<!-- /wp:html -->')
                pos += tm.end()
                continue

            # <div...>...</div> (중첩 깊이 추적)
            if raw[pos:pos+4] == '<div':
                depth = 0
                scan = pos
                while scan < len(raw):
                    next_open = raw.find('<div', scan + (1 if scan == pos else 0))
                    next_close = raw.find('</div>', scan + 1)
                    if next_close < 0:
                        scan = len(raw)
                        break
                    if scan == pos:
                        depth = 1
                        scan = pos + 4
                        continue
                    if 0 <= next_open < next_close:
                        depth += 1
                        scan = next_open + 4
                    else:
                        depth -= 1
                        if depth <= 0:
                            scan = next_close + 6
                            break
                        scan = next_close + 6
                tag = raw[pos:scan]
                blocks.append('<!-- wp:html -->\n' + tag + '\n<!-- /wp:html -->')
                pos = scan
                continue

            # <hr>
            hr_m = _re.match(r'<hr\s*/?>', raw[pos:])
            if hr_m:
                blocks.append('<!-- wp:separator -->\n<hr class="wp-block-separator"/>\n<!-- /wp:separator -->')
                pos += hr_m.end()
                continue

            # <img> 단독
            img_m = _re.match(r'(<img\b[^>]*>)', raw[pos:])
            if img_m:
                blocks.append('<!-- wp:html -->\n' + img_m.group(0) + '\n<!-- /wp:html -->')
                pos += img_m.end()
                continue

            # 기타
            next_tag = _re.search(r'<[a-zA-Z/]', raw[pos+1:])
            if next_tag:
                chunk = raw[pos:pos+1+next_tag.start()].strip()
                if chunk:
                    blocks.append('<!-- wp:html -->\n' + chunk + '\n<!-- /wp:html -->')
                pos = pos + 1 + next_tag.start()
            else:
                chunk = raw[pos:].strip()
                if chunk:
                    blocks.append('<!-- wp:html -->\n' + chunk + '\n<!-- /wp:html -->')
                break

        return '\n\n'.join(blocks)


    def _upload_image_from_url(self, image_url: str, filename: str = "featured.jpg") -> Optional[int]:
        """외부 이미지 URL을 워드프레스 미디어 라이브러리에 업로드하고 media_id 반환"""
        if not image_url or not self.is_configured():
            return None
        try:
            # 이미지 다운로드
            img_resp = requests.get(image_url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0'
            })
            if img_resp.status_code != 200:
                logger.warning(f"이미지 다운로드 실패: {img_resp.status_code}")
                return None
            
            # Content-Type 확인
            ct = img_resp.headers.get('Content-Type', 'image/jpeg')
            if 'jpeg' in ct or 'jpg' in ct:
                ext = '.jpg'
            elif 'png' in ct:
                ext = '.png'
            elif 'webp' in ct:
                ext = '.webp'
            else:
                ext = '.jpg'
            
            if not filename.endswith(ext):
                filename = filename.rsplit('.', 1)[0] + ext
            
            # 워드프레스 미디어 업로드
            headers = {
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': ct,
            }
            upload_resp = requests.post(
                f"{self.api_url}/media",
                auth=(self.username, self.password),
                headers=headers,
                data=img_resp.content,
                timeout=30
            )
            
            if upload_resp.status_code in [200, 201]:
                media_id = upload_resp.json().get('id')
                logger.info(f"WP 이미지 업로드: media_id={media_id}")
                return media_id
            else:
                logger.warning(f"WP 이미지 업로드 실패: {upload_resp.status_code}")
                return None
        except Exception as e:
            logger.warning(f"WP 이미지 업로드 오류: {e}")
            return None

    def publish(
        self,
        title: str,
        content: str,
        labels: List[str] = None,
        is_draft: bool = False,
        content_type: str = ""
    ) -> Optional[Dict]:
        """글 발행"""
        if not self.is_configured():
            logger.error("워드프레스 설정 미완료")
            return None
        
        try:
            status = "draft" if is_draft else "publish"
            
            # 블록 편집기(구텐베르크) 형식으로 변환
            block_content = self._convert_to_blocks(content)

            post_data = {
                "title": title,
                "content": block_content,
                "status": status,
            }
            
            # v2.14.0: 본문과 다른 이미지를 featured_media(썸네일)로 설정
            try:
                import re as _img_re
                from utils.food_image import get_food_image_for_platform
                # 본문에서 키워드 추출 (title 기반)
                _thumb_kw = _img_re.sub(r'[^가-힣a-zA-Z0-9 ]', '', title)[:20].strip()
                thumb_url = get_food_image_for_platform(_thumb_kw, platform='wordpress_thumb')
                if thumb_url:
                    safe_name = _img_re.sub(r'[^a-zA-Z0-9]', '-', title[:30]) + "-thumb"
                    media_id = self._upload_image_from_url(thumb_url, safe_name)
                    if media_id:
                        post_data["featured_media"] = media_id
                        logger.info(f"[WordPress] 썸네일 분리: {thumb_url[:60]}")
                else:
                    # 폴백: 본문 첫 이미지
                    img_match = _img_re.search(r'<img[^>]+src="([^"]+)"', content)
                    if img_match:
                        safe_name = _img_re.sub(r'[^a-zA-Z0-9]', '-', title[:30]) + "-thumb"
                        media_id = self._upload_image_from_url(img_match.group(1), safe_name)
                        if media_id:
                            post_data["featured_media"] = media_id
            except Exception as feat_e:
                logger.debug(f"Featured image 설정 실패: {feat_e}")
            
            if labels:
                tag_ids = self._get_or_create_tags(labels)
                if tag_ids:
                    post_data["tags"] = tag_ids
            
            # 카테고리 자동 분류
            if content_type:
                cat_id = self._get_category_id(content_type)
                if cat_id:
                    post_data["categories"] = [cat_id]
            
            response = requests.post(
                f"{self.api_url}/posts",
                auth=(self.username, self.password),
                json=post_data,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                post_url = result.get("link", "")
                status_text = "임시저장" if is_draft else "발행"
                logger.info(f"워드프레스 {status_text} 완료: {title[:30]}...")
                
                return {
                    "id": result.get("id"),
                    "url": post_url,
                    "title": title,
                    "status": "draft" if is_draft else "published",
                    "published_at": datetime.now().isoformat()
                }
            else:
                logger.error(f"워드프레스 발행 실패: {response.status_code} - {response.text[:200]}")
                return None
                
        except Exception as e:
            logger.error(f"워드프레스 발행 오류: {e}")
            return None
    
    def publish_draft(self, title: str, content: str, labels: List[str] = None, content_type: str = "") -> Optional[Dict]:
        """임시저장"""
        return self.publish(title, content, labels, is_draft=True, content_type=content_type)
    
    def _get_category_id(self, content_type: str) -> Optional[int]:
        """content_type에 매핑된 카테고리 ID 조회"""
        slug = CATEGORY_MAP.get(content_type, '')
        if not slug:
            return None
        
        try:
            response = requests.get(
                f"{self.api_url}/categories",
                auth=(self.username, self.password),
                params={"slug": slug},
                timeout=10
            )
            if response.status_code == 200:
                cats = response.json()
                if cats:
                    cat_id = cats[0]["id"]
                    logger.info(f"[WordPress] 카테고리: {content_type} → {slug} (ID: {cat_id})")
                    return cat_id
                else:
                    logger.warning(f"[WordPress] 카테고리 slug 없음: {slug}")
        except Exception as e:
            logger.warning(f"[WordPress] 카테고리 조회 실패: {e}")
        
        return None

    def _get_or_create_tags(self, tag_names: List[str]) -> List[int]:
        """태그 ID 조회 또는 생성"""
        tag_ids = []
        
        for name in tag_names:
            if not name:
                continue
            
            try:
                response = requests.get(
                    f"{self.api_url}/tags",
                    auth=(self.username, self.password),
                    params={"search": name},
                    timeout=10
                )
                
                if response.status_code == 200:
                    tags = response.json()
                    for tag in tags:
                        if tag.get("name", "").lower() == name.lower():
                            tag_ids.append(tag["id"])
                            break
                    else:
                        create_resp = requests.post(
                            f"{self.api_url}/tags",
                            auth=(self.username, self.password),
                            json={"name": name},
                            timeout=10
                        )
                        if create_resp.status_code in [200, 201]:
                            tag_ids.append(create_resp.json()["id"])
            except Exception as e:
                logger.warning(f"태그 처리 오류 ({name}): {e}")
        
        return tag_ids




def _upload_featured_image(wp_url, headers, image_url, title):
    """Featured image URL → WP media 업로드 → media_id 반환"""
    try:
        import re as _re
        img_resp = requests.get(image_url, timeout=15)
        if img_resp.status_code != 200:
            return None
        content_type = img_resp.headers.get("Content-Type", "image/webp")
        ext = content_type.split("/")[-1].split(";")[0]
        filename = _re.sub(r"[^a-zA-Z0-9가-힣-]", "", title[:30]) + f".{ext}"
        media_url = wp_url.rstrip("/") + "/wp-json/wp/v2/media"
        media_headers = {**headers, "Content-Disposition": f'attachment; filename="{filename}"', "Content-Type": content_type}
        media_resp = requests.post(media_url, headers=media_headers, data=img_resp.content, timeout=30, verify=False)
        if media_resp.status_code in (200, 201):
            return media_resp.json().get("id")
        return None
    except Exception as e:
        logger.warning(f"Featured image upload failed: {e}")
        return None


# === wp_publisher.py에서 이관 (GAP-7) ===
def publish_to_wordpress(wp_url, wp_user, wp_pass, title, body_html, categories=None, tags=None, featured_image_url=None):
    api_url = wp_url.rstrip("/") + "/wp-json/wp/v2/posts"
    token = base64.b64encode(f"{wp_user}:{wp_pass}".encode()).decode()
    headers = {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json",
    }

    post_data = {
        "title": title,
        "content": body_html,
        "status": "publish",
    }

    # featured image 업로드
    if featured_image_url:
        media_id = _upload_featured_image(wp_url, headers, featured_image_url, title)
        if media_id:
            post_data["featured_media"] = media_id

    if categories:
        post_data["categories"] = categories if isinstance(categories, list) else [categories]
    if tags:
        post_data["tags"] = tags if isinstance(tags, list) else [tags]

    try:
        resp = requests.post(api_url, json=post_data, headers=headers, timeout=30, verify=False)
        if resp.status_code in (200, 201):
            data = resp.json()
            url = data.get("link", "")
            post_id = data.get("id", "")
            logger.info(f"WP published: {title} -> {url}")
            return {"success": True, "url": url, "post_id": post_id}
        else:
            logger.error(f"WP publish failed: {resp.status_code} {resp.text[:200]}")
            return {"success": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        logger.error(f"WP publish error: {e}")
        return {"success": False, "error": str(e)}
