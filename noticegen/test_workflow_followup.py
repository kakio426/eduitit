from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import UserProfile


User = get_user_model()


class NoticeGenWorkflowFollowupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="notice_workflow_teacher",
            password="pw123456",
            email="notice_workflow_teacher@example.com",
        )
        profile = UserProfile.objects.get(user=self.user)
        profile.nickname = "알림교사"
        profile.role = "school"
        profile.save(update_fields=["nickname", "role"])
        self.client.force_login(self.user)

    def test_main_reads_workflow_seed_and_shows_origin_link(self):
        session = self.client.session
        session['workflow_action_seeds'] = {
            'workflow-seed': {
                'action': 'notice',
                'data': {
                    'target': 'parent',
                    'topic': 'notice',
                    'length_style': 'medium',
                    'keywords': '03월 08일 Science Room 이용 안내',
                    'source_label': '예약한 내용을 바탕으로 안내문 초안을 채워두었어요.',
                    'origin_url': '/reservations/test-school/?date=2026-03-08',
                    'origin_label': '예약 화면으로 돌아가기',
                },
            }
        }
        session.save()

        response = self.client.get(f"{reverse('noticegen:main')}?sb_seed=workflow-seed")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '예약한 내용을 바탕으로 안내문 초안을 채워두었어요.')
        self.assertContains(response, '예약 화면으로 돌아가기')
        self.assertContains(response, '03월 08일 Science Room 이용 안내')
    @patch("noticegen.views._call_deepseek")
    def test_generated_result_does_not_surface_followup_buttons(self, mock_call):
        mock_call.return_value = "내일은 준비물을 꼭 챙겨 주세요."

        response = self.client.post(
            reverse("noticegen:generate"),
            {
                "target": "parent",
                "topic": "notice",
                "length_style": "medium",
                "keywords": "준비물 안내",
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "내일은 준비물을 꼭 챙겨 주세요.")
        self.assertNotContains(response, "동의서로 이어서 만들기")
        self.assertNotContains(response, "서명으로 이어서 만들기")

    def test_consent_followup_is_retired(self):
        response = self.client.post(
            reverse("noticegen:start_consent_followup"),
            {
                "target": "parent",
                "topic": "notice",
                "length_style": "medium",
                "keywords": "준비물 안내",
                "result_text": "내일은 준비물을 꼭 챙겨 주세요.",
            },
        )

        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "연결 종료", status_code=410)
        session = self.client.session
        self.assertNotIn("workflow_action_seeds", session)

    def test_signature_followup_is_retired(self):
        response = self.client.post(
            reverse("noticegen:start_signature_followup"),
            {
                "target": "parent",
                "topic": "notice",
                "length_style": "medium",
                "keywords": "준비물 안내",
                "result_text": "내일은 준비물을 꼭 챙겨 주세요.",
            },
        )

        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "연결 종료", status_code=410)
        session = self.client.session
        self.assertNotIn("workflow_action_seeds", session)
