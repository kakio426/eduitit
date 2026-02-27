from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from collect.integration import BTI_SOURCE_SSAMBTI
from collect.models import CollectionRequest, Submission
from ssambti.mbti_data import MBTI_RESULTS
from ssambti.models import SsambtiResult


class SsambtiCollectIntegrationTests(TestCase):
    @patch("time.sleep", return_value=None)
    def test_analyze_auto_submits_collect_when_collect_code_present(self, _sleep):
        teacher = User.objects.create_user(username="ssam_collect_teacher", password="pw123456")
        expected_animal = MBTI_RESULTS["ESTJ"]["animal_name"]
        req = CollectionRequest.objects.create(
            creator=teacher,
            title="쌤BTI 자동연동 수합",
            allow_file=False,
            allow_link=False,
            allow_text=False,
            allow_choice=True,
            choice_mode="single",
            choice_options=[expected_animal, "코알라"],
            status="active",
        )

        payload = {"collect_code": req.access_code}
        for i in range(1, 13):
            payload[f"q{i}"] = 0

        response = self.client.post(reverse("ssambti:analyze"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "자동 전송 완료")

        result = SsambtiResult.objects.latest("created_at")
        submission = Submission.objects.get(
            collection_request=req,
            integration_source=BTI_SOURCE_SSAMBTI,
            integration_ref=f"ssambti-result-{result.id}",
        )
        self.assertEqual(submission.submission_type, "choice")
        self.assertEqual(submission.choice_answers, [expected_animal])
