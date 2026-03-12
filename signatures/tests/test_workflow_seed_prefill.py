from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class SignatureWorkflowSeedPrefillTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="signature_workflow_teacher",
            password="pw123456",
            email="signature_workflow_teacher@example.com",
        )
        self.user.userprofile.nickname = "서명교사"
        self.user.userprofile.role = "school"
        self.user.userprofile.save(update_fields=["nickname", "role"])
        self.client.force_login(self.user)

    def test_create_reads_workflow_seed_and_shows_origin_link(self):
        session = self.client.session
        session["workflow_action_seeds"] = {
            "workflow-seed": {
                "action": "signature",
                "data": {
                    "title": "준비물 확인 서명",
                    "print_title": "준비물 확인",
                    "description": "내일은 준비물을 꼭 챙겨 주세요.",
                    "source_label": "안내문 멘트에서 가져온 내용을 먼저 채워두었어요.",
                    "origin_url": "/noticegen/",
                    "origin_label": "안내문 멘트 생성기로 돌아가기",
                    "participants_text": "김하늘,보호자\n박나래,보호자",
                },
            }
        }
        session.save()

        response = self.client.get(f"{reverse('signatures:create')}?sb_seed=workflow-seed")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "안내문 멘트에서 가져온 내용을 먼저 채워두었어요.")
        self.assertContains(response, "안내문 멘트 생성기로 돌아가기")
        self.assertContains(response, "준비물 확인 서명")
        self.assertContains(response, "참석자 후보 2명")
        self.assertContains(response, 'name="sheetbook_seed_token"', html=False)
