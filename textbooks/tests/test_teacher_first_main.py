from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from happy_seed.models import HSClassroom


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

    def test_main_prioritizes_html_creation_and_sandbox_preview(self):
        response = self.client.get(reverse("textbooks:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gemini 화면과 PDF 자료를 한곳에서 점검합니다")
        self.assertContains(response, "HTML 자료")
        self.assertContains(response, "Gemini 코드 붙여넣기")
        self.assertContains(response, "Sandbox Preview")
        self.assertContains(response, "학생 참여 안내")
        self.assertNotContains(response, "PDF Live Classroom")
