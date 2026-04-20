from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import UserPolicyConsent
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
from .forms import InsightPasteForm
from .importer import parse_pasted_insight
from .models import Insight
from .templatetags.insight_extras import parse_tags


def _mark_onboarded(user, *, nickname):
    profile = user.userprofile
    profile.nickname = nickname
    profile.role = "school"
    profile.save(update_fields=["nickname", "role"])


def _grant_current_policy_consent(user):
    return UserPolicyConsent.objects.create(
        user=user,
        provider="direct",
        terms_version=TERMS_VERSION,
        privacy_version=PRIVACY_VERSION,
        agreed_at=timezone.now(),
        agreement_source="required_gate",
        ip_address="127.0.0.1",
        user_agent="insights-test-agent",
    )


class InsightModelTest(TestCase):
    def test_create_devlog_insight(self):
        insight = Insight.objects.create(
            title="My First DevLog",
            content="```python\nprint('hello')\n```",
            category="devlog",
            track="editorial",
            video_url="https://youtube.com",
        )
        self.assertEqual(insight.category, "devlog")
        self.assertEqual(insight.track, "editorial")

    def test_insight_detail_view(self):
        insight = Insight.objects.create(
            title="Detail Test",
            content="Content",
            category="devlog",
        )
        response = self.client.get(reverse("insights:detail", args=[insight.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "insights/insight_detail.html")

    def test_legacy_singular_path_redirects_to_list(self):
        response = self.client.get("/insight/", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "insights/insight_list.html")

    def test_get_video_id_supports_shorts_url(self):
        insight = Insight.objects.create(
            title="Shorts Test",
            content="Content",
            category="youtube",
            video_url="https://www.youtube.com/shorts/2bBhnfh4StU?si=test123",
        )
        self.assertEqual(insight.get_video_id(), "2bBhnfh4StU")

    def test_get_video_id_returns_none_for_non_youtube_url(self):
        insight = Insight.objects.create(
            title="External Video",
            content="Content",
            category="column",
            video_url="https://example.com/video/123",
        )
        self.assertIsNone(insight.get_video_id())

    def test_detail_shows_fallback_link_when_embed_id_missing(self):
        insight = Insight.objects.create(
            title="Blocked Embed",
            content="Content",
            category="column",
            video_url="https://example.com/video/123",
        )
        response = self.client.get(reverse("insights:detail", args=[insight.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "원본 영상 열기")
        self.assertNotContains(response, "https://www.youtube.com/embed/")

    def test_save_auto_formats_long_single_paragraph_content(self):
        insight = Insight.objects.create(
            title="Formatting",
            content="첫 문장입니다. 두 번째 문장입니다. 세 번째 문장입니다. 네 번째 문장입니다.",
            category="column",
        )
        self.assertIn("\n\n", insight.content)

    def test_detail_contains_embed_fallback_elements_for_youtube(self):
        insight = Insight.objects.create(
            title="YouTube Embed Fallback",
            content="Content",
            category="youtube",
            video_url="https://www.youtube.com/watch?v=2bBhnfh4StU",
        )
        response = self.client.get(reverse("insights:detail", args=[insight.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="insight-video-embed-shell"')
        self.assertContains(response, 'id="insight-video-fallback"')
        self.assertContains(response, insight.thumbnail_url)
        self.assertContains(response, "원본 영상 열기")


class InsightListModalTemplateTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="modal_admin",
            email="modal_admin@example.com",
            password="pw12345",
        )
        _mark_onboarded(self.admin, nickname="modal_admin_nick")
        _grant_current_policy_consent(self.admin)
        Insight.objects.create(
            title="Modal Target Insight",
            content="Body",
            category="devlog",
        )

    def test_list_uses_body_teleport_for_delete_modal(self):
        self.client.login(username="modal_admin", password="pw12345")
        response = self.client.get(reverse("insights:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'x-teleport="body"')
        self.assertContains(response, "x-transition.opacity")

    def test_list_supports_track_filter(self):
        Insight.objects.create(
            title="실전 안내문 문장",
            content="Body",
            category="column",
            track="practical",
        )
        response = self.client.get(f"{reverse('insights:list')}?track=classroom")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "수업 사례")
        self.assertNotContains(response, "실전 안내문 문장")


class InsightPermissionTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="teacher",
            email="teacher@example.com",
            password="pw12345",
        )
        _mark_onboarded(self.user, nickname="teacher_nick")

        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="pw12345",
        )
        _mark_onboarded(self.admin, nickname="admin_nick")
        _grant_current_policy_consent(self.admin)
        self.insight = Insight.objects.create(
            title="Original Title",
            content="Original Content",
            category="devlog",
        )

    def test_non_superuser_cannot_update_insight(self):
        self.client.login(username="teacher", password="pw12345")
        response = self.client.post(
            reverse("insights:update", args=[self.insight.pk]),
            {
                "title": "Changed Title",
                "track": "practical",
                "category": "column",
                "series_name": "",
                "deck": "",
                "video_url": "",
                "content": "Changed Content",
                "kakio_note": "",
                "tags": "",
            },
            follow=True,
        )

        self.insight.refresh_from_db()
        self.assertEqual(self.insight.title, "Original Title")
        self.assertRedirects(response, reverse("insights:detail", args=[self.insight.pk]))
        self.assertContains(response, "수정 권한이 없습니다.")

    def test_superuser_can_update_insight(self):
        self.client.login(username="admin", password="pw12345")
        response = self.client.post(
            reverse("insights:update", args=[self.insight.pk]),
            {
                "title": "Changed By Admin",
                "track": "classroom",
                "category": "column",
                "series_name": "교실 AI 루틴",
                "deck": "한 줄 소개",
                "video_url": "",
                "content": "Changed Content",
                "kakio_note": "note",
                "tags": "#tag",
            },
        )

        self.insight.refresh_from_db()
        self.assertEqual(self.insight.title, "Changed By Admin")
        self.assertEqual(self.insight.track, "classroom")
        self.assertEqual(self.insight.series_name, "교실 AI 루틴")
        self.assertRedirects(response, reverse("insights:detail", args=[self.insight.pk]))


class InsightPasteImportTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="teacher2",
            email="teacher2@example.com",
            password="pw12345",
        )
        _mark_onboarded(self.user, nickname="teacher2_nick")

        self.admin = User.objects.create_superuser(
            username="admin2",
            email="admin2@example.com",
            password="pw12345",
        )
        _mark_onboarded(self.admin, nickname="admin2_nick")
        _grant_current_policy_consent(self.admin)

    def _sample_blob(self):
        return (
            "Title: 테스트 인사이트 제목\n\n"
            "카테고리:\n"
            "YouTube Scrap\n"
            "Column/Essay\n\n"
            "Video url:\n"
            "https://www.youtube.com/watch?v=2bBhnfh4StU&t=450s\n\n"
            "Content:\n"
            "본문 내용입니다.\n\n"
            "Kakio note:\n"
            "노트 내용입니다.\n\n"
            "Tags:\n"
            "#태그하나, #태그둘"
        )

    def test_superuser_can_create_from_paste_blob(self):
        self.client.login(username="admin2", password="pw12345")
        response = self.client.post(
            reverse("insights:paste_create"),
            {"raw_text": self._sample_blob()},
        )

        self.assertEqual(response.status_code, 302)
        insight = Insight.objects.get(video_url="https://www.youtube.com/watch?v=2bBhnfh4StU")
        self.assertEqual(insight.category, "youtube")
        self.assertEqual(insight.tags, "#태그하나,#태그둘")
        self.assertRedirects(response, reverse("insights:detail", args=[insight.pk]))

    def test_non_superuser_cannot_access_paste_create(self):
        self.client.login(username="teacher2", password="pw12345")
        response = self.client.get(reverse("insights:paste_create"), follow=True)

        self.assertRedirects(response, reverse("insights:list"))
        self.assertContains(response, "붙여넣기 등록 권한이 없습니다.")

    def test_same_video_url_is_updated_instead_of_creating_new(self):
        existing = Insight.objects.create(
            title="기존 제목",
            content="기존 본문",
            category="column",
            video_url="https://www.youtube.com/watch?v=2bBhnfh4StU",
            tags="#기존",
        )
        self.client.login(username="admin2", password="pw12345")

        response = self.client.post(
            reverse("insights:paste_create"),
            {"raw_text": self._sample_blob()},
        )

        self.assertEqual(response.status_code, 302)
        existing.refresh_from_db()
        self.assertEqual(existing.title, "테스트 인사이트 제목")
        self.assertEqual(existing.content, "본문 내용입니다.")
        self.assertEqual(existing.tags, "#태그하나,#태그둘")
        self.assertEqual(Insight.objects.filter(video_url=existing.video_url).count(), 1)

    def test_parse_pasted_insight_accepts_mobile_and_markdown_header_variants(self):
        payload = (
            "**Title:** 테스트 인사이트 제목\n\n"
            "카테고리：\n"
            "YouTube Scrap\n"
            "Column/Essay\n\n"
            "Video url：\n"
            "https://www.youtube.com/watch?v=2bBhnfh4StU&t=450s\n\n"
            "- **Content:**\n"
            "본문 내용입니다.\n\n"
            "Kakio note：\n"
            "노트 내용입니다.\n\n"
            "Tags：\n"
            "#태그하나, #태그둘"
        )

        parsed = parse_pasted_insight(payload)

        self.assertEqual(parsed["title"], "테스트 인사이트 제목")
        self.assertEqual(parsed["content"], "본문 내용입니다.")
        self.assertEqual(parsed["video_url"], "https://www.youtube.com/watch?v=2bBhnfh4StU")
        self.assertEqual(parsed["tags"], "#태그하나,#태그둘")


class InsightPasteFormTest(TestCase):
    def test_paste_form_disables_mobile_text_corrections(self):
        attrs = InsightPasteForm().fields["raw_text"].widget.attrs

        self.assertEqual(attrs.get("autocapitalize"), "off")
        self.assertEqual(attrs.get("autocorrect"), "off")
        self.assertEqual(attrs.get("autocomplete"), "off")
        self.assertEqual(attrs.get("spellcheck"), "false")


class InsightDetailRelatedContentTest(TestCase):
    def test_detail_shows_related_sections(self):
        anchor = Insight.objects.create(
            title="대표 글",
            content="본문",
            category="column",
            track="classroom",
            series_name="교실 AI 루틴",
        )
        Insight.objects.create(
            title="같은 시리즈 글",
            content="관련 본문",
            category="column",
            track="classroom",
            series_name="교실 AI 루틴",
        )

        response = self.client.get(reverse("insights:detail", args=[anchor.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "바로 이어지는 도구")
        self.assertContains(response, "같이 보면 좋은 인사이트")
        self.assertContains(response, "같은 시리즈 글")


class InsightTemplateTagsTest(TestCase):
    def test_parse_tags_from_comma_string(self):
        tags = parse_tags("#AI,#교육,#AI")
        self.assertEqual(tags, ["#AI", "#교육"])

    def test_parse_tags_from_mixed_input(self):
        tags = parse_tags("AI, 교육\n#수업")
        self.assertEqual(tags, ["#AI", "#교육", "#수업"])
