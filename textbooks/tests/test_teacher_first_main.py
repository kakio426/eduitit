from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from happy_seed.models import HSClassroom
from textbooks.models import TextbookLiveSession, TextbookMaterial


User = get_user_model()


class TextbooksTeacherFirstMainTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="textbooks_teacher_first",
            email="textbooks_teacher_first@example.com",
            password="pw123456",
        )
        self.user.userprofile.nickname = "자료교사"
        self.user.userprofile.save(update_fields=["nickname"])
        self.client = Client()
        self.client.force_login(self.user)
        self.classroom = HSClassroom.objects.create(teacher=self.user, name="6학년 1반")
        session = self.client.session
        session["active_classroom_source"] = "hs"
        session["active_classroom_id"] = str(self.classroom.id)
        session.save()

    def test_main_prioritizes_pdf_upload_and_live_reentry(self):
        material = TextbookMaterial.objects.create(
            teacher=self.user,
            subject="SCIENCE",
            grade="6학년 1학기",
            unit_title="생태계와 환경",
            title="생태계와 환경 PDF",
            source_type=TextbookMaterial.SOURCE_PDF,
            content="교사용 메모",
            page_count=12,
            original_filename="ecosystem.pdf",
            is_published=True,
        )
        TextbookLiveSession.objects.create(
            material=material,
            teacher=self.user,
            classroom=self.classroom,
            status=TextbookLiveSession.STATUS_LIVE,
            join_code="654321",
            current_page=4,
            zoom_scale=1.0,
            viewport_json={},
        )

        response = self.client.get(reverse("textbooks:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "교과서 라이브 수업")
        self.assertContains(response, "새 PDF 올리기")
        self.assertContains(response, "PDF 올리고 수업 준비")
        self.assertContains(response, "진행 중인 수업")
        self.assertContains(response, "654321")
        self.assertContains(response, "교육자료실 바로 가기")
        self.assertNotContains(response, "HTML 자료")
        self.assertNotContains(response, "Gemini 코드 붙여넣기")
        self.assertNotContains(response, "Sandbox Preview")
