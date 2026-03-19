from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile
from infoboard.models import Board, Card, CardComment, CardReaction, Collection, SharedLink


User = get_user_model()


class InfoBoardFlowHardeningTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="teacher",
            email="teacher@example.com",
            password="pass1234",
            first_name="Teacher",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "teacher-flow"
        profile.role = "school"
        profile.save(update_fields=["nickname", "role"])
        self.client.force_login(self.user)

    def _hx_headers(self, current_path="/infoboard/"):
        return {
            "HTTP_HX_REQUEST": "true",
            "HTTP_HX_CURRENT_URL": f"http://testserver{current_path}",
        }

    def _board_payload(self, title="새 보드", **overrides):
        payload = {
            "template_preset": "question",
            "title": title,
            "description": "보드 설명",
            "icon": "❓",
            "color_theme": "blue",
            "layout": "list",
            "moderation_mode": "manual",
            "share_mode": "submit",
            "allow_student_submit": "on",
            "tag_names": "",
        }
        payload.update(overrides)
        return payload

    def _board(self, title="기본 보드", **kwargs):
        defaults = {
            "owner": self.user,
            "title": title,
            "moderation_mode": "instant",
        }
        defaults.update(kwargs)
        return Board.objects.create(**defaults)

    def _collection(self, title="기본 컬렉션", **kwargs):
        defaults = {
            "owner": self.user,
            "title": title,
        }
        defaults.update(kwargs)
        return Collection.objects.create(**defaults)

    def _shared_link(self, board, access_level="view"):
        return SharedLink.objects.create(board=board, created_by=self.user, access_level=access_level)

    def _file_card(self, board, title="파일 카드", content=""):
        uploaded = SimpleUploadedFile("guide.txt", b"hello world", content_type="text/plain")
        return Card.objects.create(
            board=board,
            title=title,
            card_type="file",
            content=content,
            file=uploaded,
            original_filename="guide.txt",
            file_size=len(b"hello world"),
        )

    def test_board_create_invalid_htmx_keeps_modal_errors(self):
        response = self.client.post(
            reverse("infoboard:board_create"),
            data=self._board_payload(title=""),
            **self._hx_headers("/infoboard/"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "입력값을 다시 확인해주세요.")
        self.assertNotIn("HX-Trigger-After-Swap", response.headers)

    def test_board_create_htmx_refreshes_grid_and_creates_share_link(self):
        response = self.client.post(
            reverse("infoboard:board_create"),
            data=self._board_payload(title="질문 보드"),
            **self._hx_headers("/infoboard/"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["HX-Retarget"], "#ibBoardGrid")
        self.assertIn("infoboard:close-modal", response.headers["HX-Trigger-After-Swap"])
        board = Board.objects.get(owner=self.user, title="질문 보드")
        self.assertEqual(board.moderation_mode, "manual")
        self.assertEqual(board.layout, "list")
        self.assertEqual(board.icon, "❓")
        self.assertTrue(board.allow_student_submit)
        self.assertEqual(board.shared_links.filter(is_active=True).count(), 1)
        self.assertEqual(board.shared_links.get(is_active=True).access_level, "submit")

    def test_board_edit_from_detail_redirects_back_to_current_detail(self):
        board = self._board(title="원래 제목", layout="timeline")
        current_path = reverse("infoboard:board_detail", args=[board.id]) + "?q=alpha"

        invalid_response = self.client.post(
            reverse("infoboard:board_edit", args=[board.id]),
            data=self._board_payload(title="", icon=board.icon, color_theme=board.color_theme, layout="timeline", moderation_mode=board.moderation_mode, share_mode="private"),
            **self._hx_headers(current_path),
        )

        self.assertEqual(invalid_response.status_code, 200)
        self.assertContains(invalid_response, "입력값을 다시 확인해주세요.")

        response = self.client.post(
            reverse("infoboard:board_edit", args=[board.id]),
            data=self._board_payload(
                title="수정된 제목",
                icon=board.icon,
                color_theme=board.color_theme,
                layout="timeline",
                moderation_mode=board.moderation_mode,
                share_mode="private",
            ),
            **self._hx_headers(current_path),
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers["HX-Redirect"], current_path)
        board.refresh_from_db()
        self.assertEqual(board.title, "수정된 제목")

    def test_legacy_timeline_board_renders_detail(self):
        board = self._board(title="타임라인 보드", layout="timeline")
        response = self.client.get(reverse("infoboard:board_detail", args=[board.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ib-card-timeline")

    def test_student_submit_uses_manual_moderation(self):
        board = self._board(title="학생 제출 보드", allow_student_submit=True, moderation_mode="manual")
        shared_link = self._shared_link(board, access_level="submit")
        submit_url = reverse("infoboard:student_submit", args=[shared_link.id])

        self.client.logout()
        response = self.client.post(
            submit_url,
            data={
                "author_name": "학생",
                "card_type": "text",
                "title": "오늘 배운 점",
                "content": "광합성 정리",
            },
            **self._hx_headers(reverse("infoboard:public_board", args=[shared_link.id])),
        )

        self.assertEqual(response.status_code, 200)
        card = Card.objects.get(board=board, title="오늘 배운 점")
        self.assertEqual(card.status, "pending")
        self.assertContains(response, "교사 확인 후 보드에 공개됩니다.")

    def test_share_permissions_split_comment_and_submit(self):
        board = self._board(title="권한 보드", allow_student_submit=True, moderation_mode="instant")
        view_link = self._shared_link(board, access_level="view")
        comment_link = self._shared_link(board, access_level="comment")
        submit_link = self._shared_link(board, access_level="submit")
        card = Card.objects.create(board=board, title="기본 카드", content="내용", card_type="text")

        self.client.logout()

        view_comment = self.client.post(
            reverse("infoboard:card_comment", args=[card.id]),
            data={"link_id": str(view_link.id), "author_name": "학생", "content": "읽기만 링크"},
        )
        self.assertEqual(view_comment.status_code, 404)

        comment_response = self.client.post(
            reverse("infoboard:card_comment", args=[card.id]),
            data={"link_id": str(comment_link.id), "author_name": "학생", "content": "댓글 가능"},
            **self._hx_headers(reverse("infoboard:public_board", args=[comment_link.id])),
        )
        self.assertEqual(comment_response.status_code, 200)
        self.assertEqual(CardComment.objects.filter(card=card).count(), 1)

        submit_comment = self.client.post(
            reverse("infoboard:card_comment", args=[card.id]),
            data={"link_id": str(submit_link.id), "author_name": "학생", "content": "제출 링크에서는 댓글 불가"},
        )
        self.assertEqual(submit_comment.status_code, 404)

        submit_allowed = self.client.get(reverse("infoboard:student_submit", args=[submit_link.id]))
        self.assertEqual(submit_allowed.status_code, 200)
        comment_submit = self.client.get(reverse("infoboard:student_submit", args=[comment_link.id]))
        self.assertEqual(comment_submit.status_code, 404)

    def test_guest_reaction_updates_existing_record(self):
        board = self._board(title="반응 보드")
        shared_link = self._shared_link(board, access_level="comment")
        card = Card.objects.create(board=board, title="반응 카드", card_type="text", content="내용")

        self.client.logout()
        reaction_url = reverse("infoboard:card_reaction", args=[card.id])
        self.client.post(reaction_url, data={"link_id": str(shared_link.id), "reaction_type": "like"})
        self.client.post(reaction_url, data={"link_id": str(shared_link.id), "reaction_type": "idea"})

        self.assertEqual(CardReaction.objects.filter(card=card).count(), 1)
        self.assertEqual(CardReaction.objects.get(card=card).reaction_type, "idea")

    def test_join_code_redirects_to_active_share_link(self):
        board = self._board(title="코드 입장 보드")
        shared_link = self._shared_link(board, access_level="view")

        self.client.logout()
        response = self.client.post(reverse("infoboard:join"), data={"code": board.access_code})

        self.assertRedirects(response, reverse("infoboard:public_board", args=[shared_link.id]), fetch_redirect_response=False)

    def test_card_moderation_publishes_pending_card(self):
        board = self._board(title="승인 보드")
        pending = Card.objects.create(board=board, title="대기 카드", card_type="text", status="pending")

        response = self.client.post(
            reverse("infoboard:card_moderate", args=[pending.id]),
            data={"action": "publish"},
            **self._hx_headers(reverse("infoboard:board_detail", args=[board.id])),
        )

        self.assertEqual(response.status_code, 200)
        pending.refresh_from_db()
        self.assertEqual(pending.status, "published")
        self.assertContains(response, "게시 카드")

    def test_download_access_rules_cover_owner_public_and_share_link(self):
        private_board = self._board(title="비공개 보드")
        private_card = self._file_card(private_board, title="비공개 파일")
        public_board = self._board(title="공개 보드", is_public=True)
        public_card = self._file_card(public_board, title="공개 파일")
        shared_board = self._board(title="공유 보드")
        shared_card = self._file_card(shared_board, title="공유 파일")
        shared_link = self._shared_link(shared_board, access_level="view")

        owner_response = self.client.get(reverse("infoboard:card_download", args=[private_card.id]))
        self.assertEqual(owner_response.status_code, 200)
        self.assertIn('attachment; filename="guide.txt"', owner_response["Content-Disposition"])

        self.client.logout()
        public_response = self.client.get(reverse("infoboard:card_download", args=[public_card.id]))
        self.assertEqual(public_response.status_code, 200)

        shared_response = self.client.get(
            reverse("infoboard:card_download", args=[shared_card.id]),
            data={"link_id": str(shared_link.id)},
        )
        self.assertEqual(shared_response.status_code, 200)

    def test_fetch_og_meta_rejects_unsafe_urls_and_returns_safe_payload(self):
        unsafe_response = self.client.get(
            reverse("infoboard:fetch_og_meta"),
            data={"url": "http://localhost:8000/path"},
        )
        self.assertEqual(unsafe_response.status_code, 400)
        self.assertIn("error", unsafe_response.json())

        with patch("core.news_ingest.assert_safe_public_url", return_value="https://example.com/path"), patch(
            "infoboard.utils.fetch_url_meta",
            return_value={"og_title": "예제 제목", "og_site_name": "example.com"},
        ):
            safe_response = self.client.get(
                reverse("infoboard:fetch_og_meta"),
                data={"url": "https://example.com/path"},
            )

        self.assertEqual(safe_response.status_code, 200)
        self.assertEqual(safe_response.json()["og_title"], "예제 제목")
