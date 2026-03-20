from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile
from products.models import Product


class BlockclassViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="blockclass_teacher",
            password="pw123456",
            email="blockclass_teacher@example.com",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "블록교사"
        profile.role = "school"
        profile.save(update_fields=["nickname", "role"])
        self.client.force_login(self.user)

    def test_main_requires_login(self):
        self.client.logout()

        response = self.client.get(reverse("blockclass:main"))

        self.assertEqual(response.status_code, 302)

    def test_main_wireframe_has_workspace_controls_and_scripts(self):
        response = self.client.get(reverse("blockclass:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "서비스 목록으로 돌아가기")
        self.assertContains(response, "시작 순서")
        self.assertContains(response, 'id="blockclass-workspace"', html=False)
        self.assertContains(response, "카테고리를 눌러 블록 고르기")
        self.assertContains(response, "blockclass-workspace-card")
        self.assertContains(response, 'id="blockclass-save-json-button"', html=False)
        self.assertContains(response, 'id="blockclass-save-image-button"', html=False)
        self.assertContains(response, 'id="blockclass-json-input"', html=False)
        self.assertContains(response, "blockclass/blockclass.js")
        self.assertContains(response, "blockly_compressed.js")

    def test_view_uses_route_name_product_fallback(self):
        Product.objects.create(
            title="블록활동 실습실",
            description="desc",
            price=0,
            is_active=True,
            launch_route_name="blockclass:main",
        )

        response = self.client.get(reverse("blockclass:main"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["service"].title, "블록활동 실습실")
