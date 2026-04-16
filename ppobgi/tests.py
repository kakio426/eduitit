from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile
from happy_seed.models import HSClassroom, HSStudent
from products.models import DTRole, DTRoleAssignment, DTStudent


class PpobgiViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="teacher",
            password="password123",
            email="teacher@example.com",
        )
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.profile.nickname = "담임교사"
        self.profile.role = "school"
        self.profile.save()

    def test_main_requires_login(self):
        response = self.client.get(reverse("ppobgi:main"))
        self.assertEqual(response.status_code, 302)

    def test_main_page_renders_for_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("ppobgi:main"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "학생 이름 명단")
        self.assertContains(response, "시작")
        self.assertContains(response, 'id="ppb-audio-btn"', html=False)
        self.assertContains(response, "다시 뽑기")
        self.assertContains(response, "방금")
        self.assertContains(response, 'id="ppb-picked-name"', html=False)
        self.assertContains(response, 'id="ppb-result-modal"', html=False)
        self.assertContains(response, 'id="ppb-result-badge"', html=False)
        self.assertContains(response, 'id="ppb-result-compliment"', html=False)
        self.assertContains(response, 'id="ppb-result-name"', html=False)
        self.assertContains(response, "사다리")
        self.assertContains(response, "순서 뽑기")
        self.assertContains(response, "팀 나누기")
        self.assertContains(response, "유성우")
        self.assertContains(response, "역할 카드")
        self.assertContains(response, "희망 포춘쿠키")
        self.assertContains(response, 'id="pps-name-input"', html=False)
        self.assertContains(response, 'id="ppt-name-input"', html=False)
        self.assertContains(response, 'id="ppm-name-input"', html=False)
        self.assertContains(response, reverse("dutyticker"))
        self.assertContains(response, 'title="반짝반짝 우리반 알림판"')
        self.assertContains(response, 'data-show-profile="premium_gameshow"', html=False)
        self.assertContains(response, f'data-storage-scope="user:{self.user.pk}"', html=False)
        self.assertContains(response, 'data-audio-pack-name="premium_gameshow_v1"', html=False)
        self.assertContains(response, 'data-audio-pack-version="1"', html=False)
        self.assertContains(response, 'data-audio-default="on"', html=False)

    def test_roster_names_returns_active_students(self):
        self.client.force_login(self.user)
        DTStudent.objects.create(user=self.user, name="3번 학생", number=3, is_active=True)
        DTStudent.objects.create(user=self.user, name="1번 학생", number=1, is_active=True)
        DTStudent.objects.create(user=self.user, name="비활성 학생", number=2, is_active=False)

        response = self.client.get(reverse("ppobgi:roster_names"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["names"], ["1번 학생", "3번 학생"])

    def test_roster_names_requires_login(self):
        response = self.client.get(reverse("ppobgi:roster_names"))
        self.assertEqual(response.status_code, 302)

    def test_classroom_students_returns_active_students_for_owner(self):
        self.client.force_login(self.user)
        classroom = HSClassroom.objects.create(teacher=self.user, name="3학년 4반")
        HSStudent.objects.create(classroom=classroom, name="3번 학생", number=3, is_active=True)
        HSStudent.objects.create(classroom=classroom, name="1번 학생", number=1, is_active=True)
        HSStudent.objects.create(classroom=classroom, name="비활성 학생", number=2, is_active=False)

        response = self.client.get(reverse("ppobgi:classroom_students", args=[classroom.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["classroom_name"], "3학년 4반")
        self.assertEqual(response.json()["names"], ["1번 학생", "3번 학생"])

    def test_classroom_students_requires_login(self):
        classroom = HSClassroom.objects.create(teacher=self.user, name="3학년 4반")

        response = self.client.get(reverse("ppobgi:classroom_students", args=[classroom.pk]))

        self.assertEqual(response.status_code, 302)

    def test_main_blocks_phone_user_agent_without_force_desktop(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("ppobgi:main"),
            HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "products/mobile_not_supported.html")
        self.assertContains(response, "교실 TV, PC, 태블릿 같은 큰 화면에 맞춰 설계된 서비스입니다.")
        self.assertContains(response, "?force_desktop=1")

    def test_main_allows_phone_user_agent_with_force_desktop(self):
        self.client.force_login(self.user)

        response = self.client.get(
            f"{reverse('ppobgi:main')}?force_desktop=1",
            HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "ppobgi/main.html")

    def test_main_template_includes_classroom_scoped_storage_key(self):
        self.client.force_login(self.user)
        classroom = HSClassroom.objects.create(teacher=self.user, name="3학년 4반")
        self.profile.default_classroom = classroom
        self.profile.save(update_fields=["default_classroom"])

        response = self.client.get(reverse("ppobgi:main"))

        self.assertContains(
            response,
            f'data-storage-scope="user:{self.user.pk}:classroom:{classroom.pk}"',
            html=False,
        )

    def test_classroom_students_returns_404_for_non_owner(self):
        other_user = User.objects.create_user(
            username="other_teacher",
            password="password123",
            email="other@example.com",
        )
        classroom = HSClassroom.objects.create(teacher=other_user, name="다른 반")
        self.client.force_login(self.user)

        response = self.client.get(reverse("ppobgi:classroom_students", args=[classroom.pk]))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"], "classroom not found")

    def test_role_cards_requires_login(self):
        response = self.client.get(reverse("ppobgi:role_cards"))
        self.assertEqual(response.status_code, 302)

    def test_role_cards_returns_active_classroom_roles(self):
        self.client.force_login(self.user)
        classroom = HSClassroom.objects.create(teacher=self.user, name="3학년 4반")
        self.profile.default_classroom = classroom
        self.profile.save(update_fields=["default_classroom"])

        student = DTStudent.objects.create(
            user=self.user,
            classroom=classroom,
            name="1번 학생",
            number=1,
            is_active=True,
        )
        role = DTRole.objects.create(
            user=self.user,
            classroom=classroom,
            name="칠판 정리",
            description="수업 뒤 칠판을 정리합니다.",
            time_slot="종례",
            icon="🧽",
        )
        DTRoleAssignment.objects.create(
            user=self.user,
            classroom=classroom,
            role=role,
            student=student,
            is_completed=True,
        )
        DTRole.objects.create(
            user=self.user,
            name="전역 역할",
            description="보이면 안 됨",
        )

        response = self.client.get(reverse("ppobgi:role_cards"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["classroom_name"], "3학년 4반")
        self.assertEqual(len(payload["roles"]), 1)
        self.assertEqual(payload["roles"][0]["role_name"], "칠판 정리")
        self.assertEqual(payload["roles"][0]["assignee_name"], "1번 학생")
        self.assertTrue(payload["roles"][0]["is_completed"])

    def test_role_cards_returns_unassigned_when_assignment_missing(self):
        self.client.force_login(self.user)
        role = DTRole.objects.create(
            user=self.user,
            name="자료 배부",
            description="학습지를 나눠줍니다.",
            time_slot="1교시 전",
            icon="📚",
        )

        response = self.client.get(reverse("ppobgi:role_cards"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["roles"][0]["role_name"], role.name)
        self.assertEqual(payload["roles"][0]["assignee_name"], "미배정")
        self.assertTrue(payload["roles"][0]["is_unassigned"])
