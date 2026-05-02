from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bamboo.models import BambooComment, BambooCommentReport, BambooConsent, BambooReport, BambooStory
from core.models import UserPolicyConsent
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION


SAFE_FABLE = """## 제목: <허세 공작새의 빈 깃털 우화>

어느 깊은 숲에 남의 도토리를 자기 깃털처럼 흔드는 공작새가 있었습니다.
부지런한 다람쥐는 조용히 바구니를 채웠지만, 공작새는 회의 나무 위에서 목청만 반짝였습니다.
숲의 친구들은 곧 깃털 사이로 텅 빈 바람만 새는 걸 알아챘습니다.
다람쥐는 다음 바구니에 더 단단한 매듭을 묶었고, 도토리 길은 분명히 남았습니다.
공작새는 혼자 우쭐댔지만, 숲은 빈 깃털보다 묵직한 발자국을 기억했습니다.

> 숲의 속삭임: 네가 한 일은 사라지지 않아요. 숲은 생각보다 잘 봅니다."""


class BambooViewTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = self._user("teacher")
        self.other = self._user("other")

    def _user(self, username):
        user = User.objects.create_user(username=username, email=f"{username}@example.com", password="pw123456")
        user.userprofile.nickname = f"{username}쌤"
        user.userprofile.role = "school"
        user.userprofile.save(update_fields=["nickname", "role"])
        UserPolicyConsent.objects.create(
            user=user,
            provider="direct",
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
            agreed_at=timezone.now(),
            agreement_source="required_gate",
        )
        return user

    @patch("bamboo.views._is_usage_limit_exceeded", return_value=False)
    @patch("bamboo.views._charge_usage_limit", return_value=False)
    @patch("bamboo.views.generate_bamboo_fable", return_value=SAFE_FABLE)
    def test_write_does_not_require_consent_and_masks_identifiers(self, _mock_llm, _mock_charge, _mock_limit):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("bamboo:write"),
            {"raw_text": "김철수 선생님이 서울새싹초등학교 5학년 3반에서 내 공을 빼앗았다."},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        story = BambooStory.objects.get()
        self.assertFalse(BambooConsent.objects.filter(user=self.user).exists())
        self.assertEqual(story.input_masked, "")
        self.assertNotIn("김철수", story.input_masked)
        self.assertNotIn("서울새싹초등학교", story.input_masked)
        self.assertEqual(response.headers.get("HX-Trigger"), "bambooPromptFlushed")

    def test_feed_and_write_pages_render(self):
        self.client.force_login(self.user)

        feed_response = self.client.get(reverse("bamboo:feed"))
        write_response = self.client.get(reverse("bamboo:write"))

        self.assertEqual(feed_response.status_code, 200)
        self.assertContains(feed_response, "우화 게시판")
        self.assertEqual(write_response.status_code, 200)
        self.assertContains(write_response, "오늘 털어놓기")
        self.assertNotContains(write_response, "특정인·학교")
        self.assertNotContains(write_response, "쓰기 전 약속")

    def test_guest_feed_and_write_pages_render_without_signup(self):
        feed_response = self.client.get(reverse("bamboo:feed"))
        write_response = self.client.get(reverse("bamboo:write"))

        self.assertEqual(feed_response.status_code, 200)
        self.assertEqual(write_response.status_code, 200)
        self.assertContains(write_response, "오늘 가능")
        self.assertNotContains(write_response, "2 / 2")
        self.assertEqual(write_response.context["usage"]["daily_limit"], 2)

    def test_member_write_page_uses_member_limit_without_count_text(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("bamboo:write"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "오늘 가능")
        self.assertNotContains(response, "5 / 5")
        self.assertEqual(response.context["usage"]["daily_limit"], 5)

    @patch("bamboo.views._is_usage_limit_exceeded", return_value=False)
    @patch("bamboo.views._charge_usage_limit", return_value=False)
    @patch("bamboo.views.generate_bamboo_fable", return_value=SAFE_FABLE)
    def test_write_masks_input_and_redirects_to_result(self, _mock_llm, _mock_charge, _mock_limit):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("bamboo:write"),
            {
                "raw_text": "김철수 선생님이 서울새싹초등학교 5학년 3반에서 내 공을 빼앗았다.",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        story = BambooStory.objects.get()
        self.assertFalse(BambooConsent.objects.filter(user=self.user).exists())
        self.assertEqual(story.input_masked, "")
        self.assertNotIn("김철수", story.input_masked)
        self.assertNotIn("서울새싹초등학교", story.input_masked)
        self.assertEqual(story.title, "허세 공작새의 빈 깃털 우화")
        self.assertEqual(story.fable_output, SAFE_FABLE)

    @patch("bamboo.views._is_usage_limit_exceeded", return_value=False)
    @patch("bamboo.views._charge_usage_limit", return_value=False)
    def test_write_retries_llm_meta_preamble(self, _mock_charge, _mock_limit):
        self.client.force_login(self.user)
        bad_fable = (
            "죄송합니다. 이전 출력에 문제가 있었습니다. 지시를 정확히 반영하여 다시 쓰겠습니다.\n\n"
            + SAFE_FABLE
        )

        with patch("bamboo.views.generate_bamboo_fable", side_effect=[bad_fable, SAFE_FABLE]) as mock_llm:
            response = self.client.post(
                reverse("bamboo:write"),
                {"raw_text": "관리자가 내 일을 자기 공처럼 말한다."},
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_llm.call_count, 2)
        story = BambooStory.objects.get()
        self.assertNotIn("죄송합니다", story.fable_output)
        self.assertEqual(story.title, "허세 공작새의 빈 깃털 우화")

    @patch("bamboo.views._is_usage_limit_exceeded", return_value=False)
    @patch("bamboo.views._charge_usage_limit", return_value=False)
    def test_write_retries_weak_fable_quality(self, _mock_charge, _mock_limit):
        self.client.force_login(self.user)
        weak_fable = """## 제목: <뜬금없는 바위 우화>

어느 깊은 숲에 바위가 있었습니다.
다람쥐가 지나갔고 바람이 불었습니다.
갑자기 모든 문제가 해결되었습니다.

> 숲의 속삭임: 오늘도 버텼어요."""

        with patch("bamboo.views.generate_bamboo_fable", side_effect=[weak_fable, SAFE_FABLE]) as mock_llm:
            response = self.client.post(
                reverse("bamboo:write"),
                {"raw_text": "관리자가 내 일을 자기 공처럼 말한다."},
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_llm.call_count, 2)
        story = BambooStory.objects.get()
        self.assertEqual(story.fable_output, SAFE_FABLE)

    @patch("bamboo.views._is_usage_limit_exceeded", return_value=False)
    @patch("bamboo.views._charge_usage_limit", return_value=False)
    def test_failed_quality_returns_message_without_http_422_or_prompt_storage(self, _mock_charge, _mock_limit):
        self.client.force_login(self.user)
        weak_fable = """## 제목: <뜬금없는 바위 우화>

어느 깊은 숲에 바위가 있었습니다.
다람쥐가 지나갔고 바람이 불었습니다.
갑자기 모든 문제가 해결되었습니다.

> 숲의 속삭임: 오늘도 버텼어요."""

        with patch("bamboo.views.generate_bamboo_fable", side_effect=[weak_fable, weak_fable]) as mock_llm:
            response = self.client.post(
                reverse("bamboo:write"),
                {"raw_text": "김철수 선생님이 서울새싹초등학교에서 이상한 말을 했다."},
                HTTP_HX_REQUEST="true",
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "조금 더 일반적으로 다시 적어주세요.")
        self.assertEqual(response.headers.get("HX-Trigger"), "bambooPromptFlushed")
        self.assertEqual(mock_llm.call_count, 2)
        self.assertEqual(BambooStory.objects.count(), 0)

    @patch("bamboo.views._is_usage_limit_exceeded", return_value=False)
    @patch("bamboo.views._charge_usage_limit", return_value=False)
    @patch("bamboo.views.generate_bamboo_fable", return_value=SAFE_FABLE)
    def test_guest_write_stores_guest_key_without_consent_step(self, _mock_llm, _mock_charge, _mock_limit):
        response = self.client.post(
            reverse("bamboo:write"),
            {
                "raw_text": "회의 때 내 일을 자기 공처럼 말해서 화난다.",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        story = BambooStory.objects.get()
        self.assertIsNone(story.author)
        self.assertTrue(story.author_guest_key)
        self.assertEqual(story.input_masked, "")
        self.assertEqual(story.title, "허세 공작새의 빈 깃털 우화")
        self.assertEqual(BambooConsent.objects.count(), 0)
        self.assertNotIn("bamboo_guest_consent_accepted", self.client.session)

    @patch("bamboo.views._is_usage_limit_exceeded", return_value=True)
    def test_usage_limit_blocks_generation(self, _mock_limit):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("bamboo:write"),
            {"raw_text": "관리자가 너무하다."},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "오늘은 충분히", status_code=429)
        self.assertEqual(BambooStory.objects.count(), 0)

    @patch("bamboo.views._is_usage_limit_exceeded", return_value=True)
    def test_guest_usage_limit_shows_signup_modal_without_explicit_counts(self, _mock_limit):
        response = self.client.post(
            reverse("bamboo:write"),
            {"raw_text": "관리자가 너무하다."},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "오늘 비회원 체험을 모두 썼어요.", status_code=429)
        self.assertContains(response, "회원가입하면 오늘 더 쓸 수 있어요.", status_code=429)
        self.assertContains(response, "회원가입", status_code=429)
        self.assertNotContains(response, "2회", status_code=429)
        self.assertNotContains(response, "2번", status_code=429)
        self.assertNotContains(response, "5회", status_code=429)
        self.assertNotContains(response, "5번", status_code=429)
        self.assertEqual(BambooStory.objects.count(), 0)

    @patch("bamboo.views.generate_bamboo_fable", return_value=SAFE_FABLE)
    def test_guest_generation_limit_blocks_after_guest_allowance(self, mock_llm):
        cache.clear()

        for index in range(2):
            response = self.client.post(
                reverse("bamboo:write"),
                {"raw_text": f"관리자가 내 일을 자기 공처럼 말한다 {index}"},
            )
            self.assertEqual(response.status_code, 302)

        blocked = self.client.post(
            reverse("bamboo:write"),
            {"raw_text": "관리자가 또 내 일을 자기 공처럼 말한다."},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(blocked.status_code, 429)
        self.assertContains(blocked, "회원가입하면 오늘 더 쓸 수 있어요.", status_code=429)
        self.assertEqual(BambooStory.objects.count(), 2)
        self.assertEqual(mock_llm.call_count, 2)

    @patch("bamboo.views.generate_bamboo_fable", return_value=SAFE_FABLE)
    def test_member_generation_limit_blocks_after_member_allowance(self, mock_llm):
        cache.clear()
        self.client.force_login(self.user)

        for index in range(5):
            response = self.client.post(
                reverse("bamboo:write"),
                {"raw_text": f"관리자가 내 일을 자기 공처럼 말한다 {index}"},
            )
            self.assertEqual(response.status_code, 302)

        blocked = self.client.post(
            reverse("bamboo:write"),
            {"raw_text": "관리자가 또 내 일을 자기 공처럼 말한다."},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(blocked.status_code, 429)
        self.assertContains(blocked, "오늘은 충분히", status_code=429)
        self.assertNotContains(blocked, "회원가입하면 오늘 더 쓸 수 있어요.", status_code=429)
        self.assertEqual(BambooStory.objects.count(), 5)
        self.assertEqual(mock_llm.call_count, 5)

    def test_report_one_keeps_story_visible_with_report_badge(self):
        story = BambooStory.objects.create(
            author=self.user,
            anon_handle="나무123",
            input_masked="관리자가 너무하다.",
            fable_output=SAFE_FABLE,
        )
        self.client.force_login(self.other)

        response = self.client.post(reverse("bamboo:report", args=[story.uuid]), HTTP_HX_REQUEST="true")

        self.assertEqual(response.status_code, 200)
        story.refresh_from_db()
        self.assertFalse(story.is_hidden_by_report)
        self.assertTrue(story.is_public)
        self.assertEqual(BambooReport.objects.filter(story=story).count(), 1)
        self.assertContains(response, "신고 접수됨")

    def test_only_author_or_staff_can_delete(self):
        story = BambooStory.objects.create(
            author=self.user,
            anon_handle="나무123",
            input_masked="관리자가 너무하다.",
            fable_output=SAFE_FABLE,
        )
        self.client.force_login(self.other)

        denied = self.client.post(reverse("bamboo:delete", args=[story.uuid]), HTTP_HX_REQUEST="true")

        self.assertEqual(denied.status_code, 403)
        self.assertTrue(BambooStory.objects.filter(pk=story.pk).exists())

        self.client.force_login(self.user)
        deleted = self.client.post(reverse("bamboo:delete", args=[story.uuid]), HTTP_HX_REQUEST="true")

        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(BambooStory.objects.filter(pk=story.pk).exists())

    def test_owner_can_delete_from_result_card(self):
        story = BambooStory.objects.create(
            author=self.user,
            anon_handle="나무123",
            input_masked="",
            fable_output=SAFE_FABLE,
        )
        self.client.force_login(self.user)

        result_page = self.client.get(reverse("bamboo:result", args=[story.uuid]))
        deleted = self.client.post(
            reverse("bamboo:delete", args=[story.uuid]),
            {"source": "result"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(result_page.status_code, 200)
        self.assertContains(result_page, "삭제")
        self.assertEqual(deleted.status_code, 200)
        self.assertContains(deleted, "삭제됨")
        self.assertFalse(BambooStory.objects.filter(pk=story.pk).exists())

    def test_owner_can_delete_from_post_detail_and_redirect_feed(self):
        story = BambooStory.objects.create(
            author=self.user,
            anon_handle="나무123",
            input_masked="",
            fable_output=SAFE_FABLE,
        )
        self.client.force_login(self.user)

        detail = self.client.get(reverse("bamboo:post", args=[story.uuid]))
        deleted = self.client.post(
            reverse("bamboo:delete", args=[story.uuid]),
            {"source": "post"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "삭제")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.headers.get("HX-Redirect"), reverse("bamboo:feed"))
        self.assertFalse(BambooStory.objects.filter(pk=story.pk).exists())

    def test_successful_submit_final_result_get_200_and_invalid_input_no_500(self):
        self.client.force_login(self.user)

        with patch("bamboo.views._is_usage_limit_exceeded", return_value=False), patch(
            "bamboo.views._charge_usage_limit", return_value=False
        ), patch("bamboo.views.generate_bamboo_fable", return_value=SAFE_FABLE):
            response = self.client.post(
                reverse("bamboo:write"),
                {"raw_text": "관리자가 내 일을 자기 공처럼 말한다."},
            )

        self.assertEqual(response.status_code, 302)
        result_response = self.client.get(response["Location"])
        self.assertEqual(result_response.status_code, 200)

        invalid_response = self.client.post(reverse("bamboo:write"), {"raw_text": ""})
        self.assertEqual(invalid_response.status_code, 400)
        self.assertContains(invalid_response, "사연을 적어주세요.", status_code=400)

    def test_feed_sorts_latest_popular_and_comments(self):
        older = BambooStory.objects.create(
            author=self.user,
            anon_handle="나무111",
            title="오래된 도토리 우화",
            input_masked="오래된 일",
            fable_output=SAFE_FABLE,
            like_count=10,
            comment_count=1,
        )
        popular = BambooStory.objects.create(
            author=self.user,
            anon_handle="나무222",
            title="인기 공작새 우화",
            input_masked="인기 일",
            fable_output=SAFE_FABLE,
            like_count=20,
            comment_count=2,
        )
        commented = BambooStory.objects.create(
            author=self.user,
            anon_handle="나무333",
            title="수다 까마귀 우화",
            input_masked="댓글 일",
            fable_output=SAFE_FABLE,
            like_count=1,
            comment_count=9,
        )
        self.client.force_login(self.other)

        latest_response = self.client.get(reverse("bamboo:feed"))
        popular_response = self.client.get(reverse("bamboo:feed"), {"sort": "popular"})
        comments_response = self.client.get(reverse("bamboo:feed"), {"sort": "comments"})

        self.assertEqual(list(latest_response.context["stories"]), [commented, popular, older])
        self.assertEqual(popular_response.context["stories"][0], popular)
        self.assertEqual(comments_response.context["stories"][0], commented)

    def test_public_post_get_200_and_view_count_once_per_session(self):
        story = BambooStory.objects.create(
            author=self.user,
            anon_handle="나무123",
            title="허세 공작새의 빈 깃털 우화",
            input_masked="관리자가 너무하다.",
            fable_output=SAFE_FABLE,
        )
        self.client.force_login(self.other)

        first = self.client.get(reverse("bamboo:post", args=[story.uuid]))
        second = self.client.get(reverse("bamboo:post", args=[story.uuid]))

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        story.refresh_from_db()
        self.assertEqual(story.view_count, 1)
        self.assertContains(first, "댓글 0")

    def test_comment_create_blocks_identifier_and_stores_only_masked_body(self):
        story = BambooStory.objects.create(
            author=self.user,
            anon_handle="나무123",
            title="허세 공작새의 빈 깃털 우화",
            input_masked="관리자가 너무하다.",
            fable_output=SAFE_FABLE,
        )
        self.client.force_login(self.other)

        blocked = self.client.post(
            reverse("bamboo:comment_create", args=[story.uuid]),
            {"body": "서울새싹초등학교 김철수 선생님 생각남"},
            HTTP_HX_REQUEST="true",
        )
        blocked_expression = self.client.post(
            reverse("bamboo:comment_create", args=[story.uuid]),
            {"body": "씨발 이거 진짜 웃기다"},
            HTTP_HX_REQUEST="true",
        )
        created = self.client.post(
            reverse("bamboo:comment_create", args=[story.uuid]),
            {"body": "빈 깃털 표현 진짜 웃기다"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(blocked.status_code, 400)
        self.assertContains(blocked, "특정 정보는 빼고 써주세요.", status_code=400)
        self.assertEqual(blocked_expression.status_code, 400)
        self.assertContains(blocked_expression, "표현을 조금 순하게 바꿔주세요.", status_code=400)
        self.assertEqual(created.status_code, 200)
        comment = BambooComment.objects.get()
        self.assertEqual(comment.body_masked, "빈 깃털 표현 진짜 웃기다")
        story.refresh_from_db()
        self.assertEqual(story.comment_count, 1)

    def test_guest_comment_can_delete_own_comment_only_by_same_session(self):
        story = BambooStory.objects.create(
            author=self.user,
            anon_handle="나무123",
            title="허세 공작새의 빈 깃털 우화",
            input_masked="관리자가 너무하다.",
            fable_output=SAFE_FABLE,
        )

        created = self.client.post(
            reverse("bamboo:comment_create", args=[story.uuid]),
            {"body": "숲이 다 봤다"},
            HTTP_HX_REQUEST="true",
        )
        comment = BambooComment.objects.get()
        other_client = self.client_class()
        denied = other_client.post(reverse("bamboo:comment_delete", args=[story.uuid, comment.id]), HTTP_HX_REQUEST="true")
        deleted = self.client.post(reverse("bamboo:comment_delete", args=[story.uuid, comment.id]), HTTP_HX_REQUEST="true")

        self.assertEqual(created.status_code, 200)
        self.assertIsNone(comment.author)
        self.assertTrue(comment.author_guest_key)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(BambooComment.objects.filter(pk=comment.pk).exists())

    def test_comment_delete_authorization_and_report_keeps_comment_visible(self):
        story = BambooStory.objects.create(
            author=self.user,
            anon_handle="나무123",
            title="허세 공작새의 빈 깃털 우화",
            input_masked="관리자가 너무하다.",
            fable_output=SAFE_FABLE,
        )
        comment = BambooComment.objects.create(
            story=story,
            author=self.other,
            anon_handle="나무456",
            body_masked="숲이 다 봤다",
        )
        story.comment_count = 1
        story.save(update_fields=["comment_count"])

        self.client.force_login(self.user)
        denied = self.client.post(reverse("bamboo:comment_delete", args=[story.uuid, comment.id]), HTTP_HX_REQUEST="true")
        reported = self.client.post(reverse("bamboo:comment_report", args=[story.uuid, comment.id]), HTTP_HX_REQUEST="true")

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(reported.status_code, 200)
        comment.refresh_from_db()
        story.refresh_from_db()
        self.assertFalse(comment.is_hidden_by_report)
        self.assertEqual(story.comment_count, 1)
        self.assertEqual(BambooCommentReport.objects.filter(comment=comment).count(), 1)
        self.assertContains(reported, "신고 접수됨")
