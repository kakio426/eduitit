import zipfile
from datetime import date

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from autoarticle.models import GeneratedArticle


class AutoarticleRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reg_user", password="pass1234")
        self.client.login(username="reg_user", password="pass1234")
        self.article = GeneratedArticle.objects.create(
            user=self.user,
            school_name="테스트 초등학교",
            grade="3학년",
            class_name="2반",
            event_name="과학 체험",
            location="강당",
            event_date=date.today(),
            tone="친근한",
            keywords="실험, 체험",
            title="과학 체험 소식",
            content_summary="핵심 요약 1\n핵심 요약 2",
            full_text="오늘은 과학 체험 활동을 진행했습니다.",
            hashtags=["과학", "체험"],
            images=[],
        )

    def test_archive_page_loads_without_server_error(self):
        response = self.client.get(reverse("autoarticle:archive"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "기사 보관함")

    def test_ppt_download_regenerates_when_cached_file_is_invalid(self):
        self.article.ppt_file.save("broken_cache.pptx", ContentFile(b"fake ppt content"), save=True)
        self.assertFalse(zipfile.is_zipfile(self.article.ppt_file.path))

        response = self.client.get(reverse("autoarticle:ppt_download", kwargs={"pk": self.article.pk}))
        self.assertEqual(response.status_code, 200)

        self.article.refresh_from_db()
        self.assertTrue(self.article.ppt_file)
        self.assertTrue(zipfile.is_zipfile(self.article.ppt_file.path))
