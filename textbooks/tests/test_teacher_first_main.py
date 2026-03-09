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

    def test_main_keeps_create_and_library_primary_and_demotes_student_join_info(self):
        response = self.client.get(reverse("textbooks:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "수업 자료를 저장하고 바로 수업에 씁니다")
        self.assertContains(response, "새 자료 추가")
        self.assertContains(response, "저장한 자료")
        self.assertContains(response, "학생 참여 안내")
        self.assertNotContains(response, "교사용 PDF 업로드, TV 발표 화면, 학생 태블릿 동기화, 기본 필기까지 한 흐름으로 연결하는 수업 자료실입니다.")
        self.assertNotContains(response, "PDF Live Classroom")
