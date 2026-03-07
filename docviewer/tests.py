from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile
from products.models import Product


class DocviewerViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="docviewer_teacher",
            password="pw123456",
            email="docviewer_teacher@example.com",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "문서교사"
        profile.role = "school"
        profile.save(update_fields=["nickname", "role"])
        self.client.force_login(self.user)

    def test_main_requires_login(self):
        self.client.logout()

        response = self.client.get(reverse("docviewer:main"))

        self.assertEqual(response.status_code, 302)

    def test_main_wireframe_has_next_action_controls(self):
        response = self.client.get(reverse("docviewer:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "서비스 목록으로 돌아가기")
        self.assertContains(response, "교사 작업 흐름")
        self.assertContains(response, "PDF를 선택하면 오른쪽에서 바로 확인할 수 있어요.")
        self.assertContains(response, 'id="docviewer-file-input"', html=False)
        self.assertContains(response, 'id="docviewer-prev-button"', html=False)
        self.assertContains(response, 'id="docviewer-next-button"', html=False)
        self.assertContains(response, "인쇄하기 (새 탭)")
        self.assertContains(response, "docviewer/docviewer.js")

    def test_view_uses_route_name_product_fallback(self):
        Product.objects.create(
            title="문서 미리보기실",
            description="desc",
            price=0,
            is_active=True,
            launch_route_name="docviewer:main",
        )

        response = self.client.get(reverse("docviewer:main"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["service"].title, "문서 미리보기실")
