"""URL 메타데이터 추출 유틸리티 (OG 태그)."""
import logging
from urllib.parse import urljoin, urlparse

from core.news_ingest import UnsafeNewsUrlError, _safe_fetch

logger = logging.getLogger(__name__)

# 타임아웃 (초)
REQUEST_TIMEOUT = 5


def fetch_url_meta(url: str) -> dict:
    """
    URL에서 OG 태그를 추출해 dict로 반환.
    {'og_title': ..., 'og_description': ..., 'og_image': ..., 'og_site_name': ...}
    실패 시 빈 dict 반환 (에러 로깅만, 예외 전파 안 함).
    """
    if not url:
        return {}

    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning('[InfoBoard] requests 또는 beautifulsoup4 미설치 — OG 추출 건너뜀')
        return {}

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; EduItIt-InfoBoard/1.0)',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
        }
        resp, final_url = _safe_fetch(
            url,
            timeout=REQUEST_TIMEOUT,
            headers=headers,
        )
        resp.raise_for_status()

        # 텍스트가 아닌 응답 무시
        content_type = resp.headers.get('Content-Type', '')
        if 'text/html' not in content_type and 'application/xhtml' not in content_type:
            return {}

        soup = BeautifulSoup(resp.text[:50000], 'html.parser')  # 상위 50KB만 파싱

        meta = {}

        # OG 태그 우선
        og_title = soup.find('meta', property='og:title')
        og_desc = soup.find('meta', property='og:description')
        og_image = soup.find('meta', property='og:image')
        og_site = soup.find('meta', property='og:site_name')

        if og_title:
            meta['og_title'] = (og_title.get('content') or '')[:500]
        if og_desc:
            meta['og_description'] = (og_desc.get('content') or '')[:1000]
        if og_image:
            img_url = og_image.get('content') or ''
            if img_url:
                meta['og_image'] = urljoin(final_url, img_url)[:1000]
        if og_site:
            meta['og_site_name'] = (og_site.get('content') or '')[:200]

        # OG 없으면 title/meta description 폴백
        if 'og_title' not in meta:
            title_tag = soup.find('title')
            if title_tag and title_tag.string:
                meta['og_title'] = title_tag.string.strip()[:500]

        if 'og_description' not in meta:
            desc_tag = soup.find('meta', attrs={'name': 'description'})
            if desc_tag:
                meta['og_description'] = (desc_tag.get('content') or '')[:1000]

        if 'og_site_name' not in meta:
            meta['og_site_name'] = urlparse(final_url).netloc

        return meta

    except UnsafeNewsUrlError as exc:
        logger.warning(f'[InfoBoard] Unsafe OG URL blocked: {url} — {exc}')
        return {}
    except Exception as e:
        logger.warning(f'[InfoBoard] OG 추출 실패: {url} — {e}')
        return {}
