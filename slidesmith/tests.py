from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile
from products.models import Product

from .utils import build_slide_deck


class SlidesmithUtilsTests(TestCase):
    def test_build_slide_deck_creates_cover_and_content_slides(self):
        deck = build_slide_deck(
            "학급 설명회",
            "학급 운영 방향\n- 하루 흐름 안내\n---\n준비물\n- 개인 물통",
        )

        self.assertEqual(deck["slide_count"], 3)
        self.assertEqual(deck["slides"][0].kind, "cover")
        self.assertEqual(deck["slides"][1].title, "학급 운영 방향")
        self.assertEqual(deck["slides"][2].bullets[0], "개인 물통")


class SlidesmithViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="slidesmith_teacher",
            password="pw123456",
            email="slidesmith_teacher@example.com",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "발표교사"
        profile.role = "school"
        profile.save(update_fields=["nickname", "role"])
        self.client.force_login(self.user)

    def test_main_requires_login(self):
        self.client.logout()

        response = self.client.get(reverse("slidesmith:main"))

        self.assertEqual(response.status_code, 302)

    def test_main_wireframe_has_editor_preview_and_actions(self):
        response = self.client.get(reverse("slidesmith:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "홈으로 돌아가기")
        self.assertContains(response, "발표 자료 만들기")
        self.assertContains(response, 'id="slidesmith-form"', html=False)
        self.assertContains(response, 'id="slidesmith-title-input"', html=False)
        self.assertContains(response, 'id="slidesmith-text-input"', html=False)
        self.assertContains(response, 'id="slidesmith-present-button"', html=False)
        self.assertContains(response, "발표 시작 (새 탭)")
        self.assertContains(response, "slidesmith/slidesmith.js")
        self.assertNotContains(response, "슬라이드 구분선")
        self.assertNotContains(response, "교사 발표 흐름")
        self.assertNotContains(response, "PDF 저장 안내")

    def test_present_renders_posted_slides(self):
        response = self.client.post(
            reverse("slidesmith:present"),
            {
                "presentation_title": "협의회 자료",
                "presentation_text": "회의 안건\n- 시간표 점검\n---\n정리\n- 다음 일정",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "협의회 자료")
        self.assertContains(response, "회의 안건")
        self.assertContains(response, "다음 일정")
        self.assertContains(response, 'id="slidesmith-presentation-status"', html=False)

    def test_view_uses_route_name_product_fallback(self):
        Product.objects.create(
            title="수업 발표 메이커",
            description="desc",
            price=0,
            is_active=True,
            launch_route_name="slidesmith:main",
        )

        response = self.client.get(reverse("slidesmith:main"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["service"].title, "수업 발표 메이커")
