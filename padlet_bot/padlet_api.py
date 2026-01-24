"""
패들릿 API 클라이언트

패들릿 API를 사용하여 보드와 게시물을 가져옵니다.
API 문서: https://padlet.dev/
"""

import os
import re
import requests
from typing import Optional, List, Dict
from dataclasses import dataclass


@dataclass
class PadletPost:
    """패들릿 게시물"""
    id: str
    subject: str
    body: str
    author: str
    created_at: str
    attachment_url: Optional[str] = None


@dataclass
class PadletBoard:
    """패들릿 보드"""
    id: str
    title: str
    description: str
    posts: List[PadletPost]


class PadletAPIClient:
    """패들릿 API 클라이언트"""

    BASE_URL = "https://api.padlet.dev/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('PADLET_API_KEY', '')
        if not self.api_key:
            raise ValueError("PADLET_API_KEY가 설정되지 않았습니다.")

        self.headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """API 요청 실행"""
        url = f"{self.BASE_URL}{endpoint}"
        response = requests.request(
            method,
            url,
            headers=self.headers,
            timeout=30,
            **kwargs
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def extract_board_id_from_url(url: str) -> Optional[str]:
        """
        패들릿 URL에서 보드 ID 추출

        지원 형식:
        - https://padlet.com/username/boardname-abc123def
        - https://padlet.com/username/abc123def
        - 직접 ID 입력
        """
        # URL 패턴 매칭
        patterns = [
            r'padlet\.com/[^/]+/[^/]+-([a-zA-Z0-9]+)$',  # username/title-id
            r'padlet\.com/[^/]+/([a-zA-Z0-9]+)$',        # username/id
            r'^([a-zA-Z0-9]{8,})$',                       # 직접 ID
        ]

        for pattern in patterns:
            match = re.search(pattern, url.strip())
            if match:
                return match.group(1)

        return None

    def get_board(self, board_id: str) -> dict:
        """보드 정보 가져오기"""
        return self._request("GET", f"/boards/{board_id}")

    def get_posts(self, board_id: str) -> List[dict]:
        """보드의 모든 게시물 가져오기"""
        result = self._request("GET", f"/boards/{board_id}/posts")
        return result.get("data", [])

    def fetch_board_with_posts(self, board_id_or_url: str) -> PadletBoard:
        """보드와 모든 게시물 가져오기"""
        # URL에서 ID 추출
        board_id = self.extract_board_id_from_url(board_id_or_url)
        if not board_id:
            board_id = board_id_or_url

        # 보드 정보 가져오기
        board_data = self.get_board(board_id)
        board_info = board_data.get("data", {}).get("attributes", {})

        # 게시물 가져오기
        posts_data = self.get_posts(board_id)

        posts = []
        for post in posts_data:
            attrs = post.get("attributes", {})
            posts.append(PadletPost(
                id=post.get("id", ""),
                subject=attrs.get("subject", "") or "",
                body=attrs.get("body", "") or "",
                author=attrs.get("author_name", "") or "익명",
                created_at=attrs.get("created_at", ""),
                attachment_url=attrs.get("attachment_url"),
            ))

        return PadletBoard(
            id=board_id,
            title=board_info.get("title", "제목 없음"),
            description=board_info.get("description", ""),
            posts=posts,
        )

    def posts_to_text(self, board: PadletBoard) -> str:
        """게시물을 텍스트로 변환 (RAG용)"""
        texts = []

        # 보드 정보
        texts.append(f"# {board.title}")
        if board.description:
            texts.append(f"설명: {board.description}")
        texts.append("")

        # 각 게시물
        for i, post in enumerate(board.posts, 1):
            post_text = f"## 게시물 {i}"
            if post.subject:
                post_text += f"\n제목: {post.subject}"
            if post.body:
                post_text += f"\n내용: {post.body}"
            if post.author:
                post_text += f"\n작성자: {post.author}"
            texts.append(post_text)

        return "\n\n".join(texts)


def get_padlet_client() -> Optional[PadletAPIClient]:
    """패들릿 API 클라이언트 인스턴스 반환"""
    try:
        return PadletAPIClient()
    except ValueError:
        return None


def is_padlet_api_configured() -> bool:
    """패들릿 API가 설정되어 있는지 확인"""
    return bool(os.environ.get('PADLET_API_KEY', ''))
