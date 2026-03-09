from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class ConsentWorkflowSeedPrefillTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username="consent_workflow_teacher",
            password="pw123456",
            email="consent_workflow_teacher@example.com",
        )
        self.teacher.userprofile.nickname = "동의교사"
        self.teacher.userprofile.role = "school"
        self.teacher.userprofile.save(update_fields=["nickname", "role"])
        self.client.force_login(self.teacher)

    def test_create_step1_reads_workflow_seed_and_shows_origin_link(self):
        session = self.client.session
        session["workflow_action_seeds"] = {
            "workflow-seed": {
                "action": "consent",
                "data": {
                    "document_title": "준비물 안내문",
                    "title": "준비물 동의서",
                    "message": "준비물을 꼭 챙겨 주세요.",
                    "source_label": "안내문 멘트에서 가져온 내용을 먼저 채워두었어요.",
                    "origin_url": "/noticegen/",
                    "origin_label": "안내문 멘트 생성기로 돌아가기",
                },
            }
        }
        session.save()

        response = self.client.get(f"{reverse('consent:create_step1')}?sb_seed=workflow-seed")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "안내문 멘트에서 가져온 내용을 먼저 채워두었어요.")
        self.assertContains(response, "안내문 멘트 생성기로 돌아가기")
        self.assertContains(response, "준비물을 꼭 챙겨 주세요.")
