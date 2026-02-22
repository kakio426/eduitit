from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Insight


class InsightModelTest(TestCase):
    def test_create_devlog_insight(self):
        insight = Insight.objects.create(
            title="My First DevLog",
            content="```python\nprint('hello')\n```",
            category="devlog",
            video_url="https://youtube.com",
        )
        self.assertEqual(insight.category, "devlog")

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


class InsightPermissionTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="teacher",
            email="teacher@example.com",
            password="pw12345",
        )
        self.user.userprofile.nickname = "teacher_nick"
        self.user.userprofile.save(update_fields=["nickname"])

        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="pw12345",
        )
        self.admin.userprofile.nickname = "admin_nick"
        self.admin.userprofile.save(update_fields=["nickname"])
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
                "category": "column",
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
                "category": "column",
                "video_url": "",
                "content": "Changed Content",
                "kakio_note": "note",
                "tags": "#tag",
            },
        )

        self.insight.refresh_from_db()
        self.assertEqual(self.insight.title, "Changed By Admin")
        self.assertRedirects(response, reverse("insights:detail", args=[self.insight.pk]))


class InsightPasteImportTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="teacher2",
            email="teacher2@example.com",
            password="pw12345",
        )
        self.user.userprofile.nickname = "teacher2_nick"
        self.user.userprofile.save(update_fields=["nickname"])

        self.admin = User.objects.create_superuser(
            username="admin2",
            email="admin2@example.com",
            password="pw12345",
        )
        self.admin.userprofile.nickname = "admin2_nick"
        self.admin.userprofile.save(update_fields=["nickname"])

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

    def test_authenticated_user_can_access_paste_create(self):
        self.client.login(username="teacher2", password="pw12345")
        response = self.client.get(reverse("insights:paste_create"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "insights/insight_paste_form.html")

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
