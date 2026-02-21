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
