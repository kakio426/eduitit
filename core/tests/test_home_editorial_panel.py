from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile
from insights.models import Insight


def _create_home_user(username):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="pw12345",
    )
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.nickname = f"{username}_nick"
    profile.role = "school"
    profile.save()
    return user


class HomeEditorialPanelTest(TestCase):
    def test_authenticated_home_shows_editorial_panel_and_prompt_chip(self):
        user = _create_home_user("editorial_home")
        Insight.objects.create(
            title="교실에 바로 쓰는 AI 문장",
            content="수업 전에 바로 꺼내 쓸 수 있는 문장을 정리했습니다.",
            deck="오늘 바로 쓰는 한 줄",
            category="column",
            track="practical",
            is_featured=True,
        )

        self.client.login(username=user.username, password="pw12345")
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-home-v6-editorial-panel="true"', html=False)
        self.assertContains(response, "교실 AI 인사이트")
        self.assertContains(response, "교실에 바로 쓰는 AI 문장")
        self.assertContains(response, "인사이트로 질문 시작")
        self.assertContains(response, "교무비서로 이어쓰기")

    def test_editorial_routes_smoke(self):
        user = _create_home_user("editorial_smoke")
        insight = Insight.objects.create(
            title="수업 사례 스모크",
            content="수업 사례 상세 진입과 목록 재노출을 확인합니다.",
            deck="교실 흐름 스모크",
            category="column",
            track="classroom",
        )

        self.client.login(username=user.username, password="pw12345")

        home_response = self.client.get(reverse("home"))
        community_response = self.client.get(reverse("community_feed"), follow=True)
        list_response = self.client.get(reverse("insights:list"))
        detail_response = self.client.get(reverse("insights:detail", args=[insight.pk]))

        self.assertEqual(home_response.status_code, 200)
        self.assertEqual(community_response.status_code, 200)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
