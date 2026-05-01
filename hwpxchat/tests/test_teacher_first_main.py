from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile


class HwpxChatTeacherFirstMainTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="hwpx_teacher_first",
            password="pw123456",
            email="hwpx_teacher_first@example.com",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "문서교사"
        profile.role = "school"
        profile.save(update_fields=["nickname", "role"])
        self.client.force_login(self.user)

    def test_main_uses_compact_help_instead_of_long_explainer(self):
        response = self.client.get(reverse("hwpxchat:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "공문을 오늘 할 일로 바로 정리하기")
        self.assertContains(response, "HWPX로 저장하는 방법")
        self.assertContains(response, 'hx-encoding="multipart/form-data"')
        self.assertContains(response, "htmx:beforeSwap")
        self.assertNotContains(response, "문서 대화 방식")
        self.assertNotContains(response, "문서만 올리면 바로 정리됩니다")
        self.assertNotContains(response, "교무수첩")
        self.assertNotContains(response, "왜 이 도구를 쓰나요?")
        self.assertNotContains(response, "사용 방법")
        self.assertNotContains(response, "서비스 목록으로 돌아가기")

    def test_main_keeps_failures_inside_page_without_modal_blockers(self):
        response = self.client.get(reverse("hwpxchat:main"))
        template = Path("hwpxchat/templates/hwpxchat/main.html").read_text(
            encoding="utf-8"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "공문이나 한글 문서를 올리면 해야 할 일")
        self.assertContains(response, 'id="hwpx-upload-status"', html=False)
        self.assertContains(response, 'id="hwpx-copy-status"', html=False)
        self.assertNotIn("fixed inset-0", template)
        self.assertNotIn("z-[120]", template)
        self.assertNotIn("Swal", template)
        self.assertNotIn("response.json()", template)
