from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from collect.models import CollectionRequest, Submission


class ChoiceSubmissionTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username="choice_teacher",
            email="choice_teacher@example.com",
            password="pw123456",
        )
        self.teacher.userprofile.nickname = "choice-teacher"
        self.teacher.userprofile.save(update_fields=["nickname"])

    def test_request_create_requires_at_least_one_submission_type(self):
        self.client.force_login(self.teacher)
        response = self.client.post(
            reverse("collect:request_create"),
            data={
                "title": "선택형 설정 테스트",
                "description": "",
                "expected_submitters": "",
                "deadline": "",
                "max_submissions": 10,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "제출 허용 방식은 최소 1개 이상 선택해주세요.")

    def test_submit_process_blocks_disallowed_submission_type(self):
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="선택형만 허용",
            allow_file=False,
            allow_link=False,
            allow_text=False,
            allow_choice=True,
            choice_mode="single",
            choice_options=["찬성", "반대"],
            status="active",
        )
        upload = SimpleUploadedFile("sample.txt", b"hello", content_type="text/plain")

        response = self.client.post(
            reverse("collect:submit_process", args=[req.id]),
            data={
                "contributor_name": "학생1",
                "submission_type": "file",
                "file": upload,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "해당 제출 유형을 사용할 수 없습니다.")
        self.assertFalse(Submission.objects.filter(collection_request=req).exists())

    def test_submit_choice_single_success(self):
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="찬반 투표",
            allow_file=False,
            allow_link=False,
            allow_text=False,
            allow_choice=True,
            choice_mode="single",
            choice_options=["찬성", "반대"],
            status="active",
        )

        response = self.client.post(
            reverse("collect:submit_process", args=[req.id]),
            data={
                "contributor_name": "학생2",
                "submission_type": "choice",
                "choice_answers": "찬성",
            },
        )

        self.assertEqual(response.status_code, 302)
        submission = Submission.objects.get(collection_request=req, contributor_name="학생2")
        self.assertEqual(submission.submission_type, "choice")
        self.assertEqual(submission.choice_answers, ["찬성"])
        self.assertEqual(submission.choice_other_text, "")

    def test_submit_choice_multi_respects_min_and_max(self):
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="복수 선택",
            allow_file=False,
            allow_link=False,
            allow_text=False,
            allow_choice=True,
            choice_mode="multi",
            choice_options=["A", "B", "C"],
            choice_min_selections=2,
            choice_max_selections=2,
            status="active",
        )

        response = self.client.post(
            reverse("collect:submit_process", args=[req.id]),
            data={
                "contributor_name": "학생3",
                "submission_type": "choice",
                "choice_answers": ["A"],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "최소 2개 이상 선택해주세요.")
        self.assertFalse(Submission.objects.filter(collection_request=req, contributor_name="학생3").exists())

    def test_submit_choice_allows_other_text(self):
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="기타 허용",
            allow_file=False,
            allow_link=False,
            allow_text=False,
            allow_choice=True,
            choice_mode="single",
            choice_options=["A", "B"],
            choice_allow_other=True,
            status="active",
        )

        response = self.client.post(
            reverse("collect:submit_process", args=[req.id]),
            data={
                "contributor_name": "학생4",
                "submission_type": "choice",
                "choice_answers": "__other__",
                "choice_other_text": "직접 입력 답안",
            },
        )

        self.assertEqual(response.status_code, 302)
        submission = Submission.objects.get(collection_request=req, contributor_name="학생4")
        self.assertEqual(submission.choice_answers, [])
        self.assertEqual(submission.choice_other_text, "직접 입력 답안")

    def test_export_csv_includes_choice_summary(self):
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="CSV 테스트",
            allow_file=False,
            allow_link=False,
            allow_text=False,
            allow_choice=True,
            choice_mode="multi",
            choice_options=["A", "B", "C"],
            choice_min_selections=1,
            status="active",
        )
        Submission.objects.create(
            collection_request=req,
            contributor_name="학생5",
            submission_type="choice",
            choice_answers=["A", "B"],
            choice_other_text="직접",
        )

        self.client.force_login(self.teacher)
        response = self.client.get(reverse("collect:export_csv", args=[req.id]))

        self.assertEqual(response.status_code, 200)
        csv_text = response.content.decode("utf-8-sig")
        self.assertIn("A, B, 기타: 직접", csv_text)

    def test_request_detail_builds_choice_stats_for_dashboard(self):
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="통계 대시보드",
            allow_file=False,
            allow_link=False,
            allow_text=False,
            allow_choice=True,
            choice_mode="multi",
            choice_options=["A", "B", "C"],
            choice_allow_other=True,
            status="active",
        )
        Submission.objects.create(
            collection_request=req,
            contributor_name="학생1",
            submission_type="choice",
            choice_answers=["A", "B"],
        )
        Submission.objects.create(
            collection_request=req,
            contributor_name="학생2",
            submission_type="choice",
            choice_answers=["B"],
        )
        Submission.objects.create(
            collection_request=req,
            contributor_name="학생3",
            submission_type="choice",
            choice_answers=[],
            choice_other_text="직접 입력",
        )

        self.client.force_login(self.teacher)
        response = self.client.get(reverse("collect:request_detail", args=[req.id]))

        self.assertEqual(response.status_code, 200)
        choice_stats = response.context["choice_stats"]
        self.assertTrue(choice_stats["enabled"])
        self.assertTrue(choice_stats["is_multi"])
        self.assertEqual(choice_stats["response_count"], 3)
        self.assertEqual(choice_stats["total_picks"], 4)
        self.assertEqual(choice_stats["top_label"], "B")
        self.assertEqual(choice_stats["top_count"], 2)

        by_label = {item["label"]: item for item in choice_stats["items"]}
        self.assertEqual(by_label["A"]["count"], 1)
        self.assertEqual(by_label["B"]["count"], 2)
        self.assertEqual(by_label["기타"]["count"], 1)

    def test_choice_stats_partial_renders_dashboard_copy(self):
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="통계 부분 갱신",
            allow_file=False,
            allow_link=False,
            allow_text=False,
            allow_choice=True,
            choice_mode="single",
            choice_options=["찬성", "반대"],
            status="active",
        )
        Submission.objects.create(
            collection_request=req,
            contributor_name="학생1",
            submission_type="choice",
            choice_answers=["찬성"],
        )

        self.client.force_login(self.teacher)
        response = self.client.get(reverse("collect:choice_stats_partial", args=[req.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "선택형 응답 대시보드")
        self.assertContains(response, "응답자 대비")
        self.assertContains(response, "선택 비중")

    def test_submissions_partial_filters_by_choice_option(self):
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="필터 테스트",
            allow_file=False,
            allow_link=False,
            allow_text=False,
            allow_choice=True,
            choice_mode="multi",
            choice_options=["A", "B", "C"],
            choice_allow_other=True,
            status="active",
        )
        Submission.objects.create(
            collection_request=req,
            contributor_name="학생A",
            submission_type="choice",
            choice_answers=["A"],
        )
        Submission.objects.create(
            collection_request=req,
            contributor_name="학생B",
            submission_type="choice",
            choice_answers=["B"],
        )
        Submission.objects.create(
            collection_request=req,
            contributor_name="학생기타",
            submission_type="choice",
            choice_answers=[],
            choice_other_text="직접",
        )

        self.client.force_login(self.teacher)
        response = self.client.get(
            reverse("collect:submissions_partial", args=[req.id]),
            data={"choice_filter": "option::A"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "학생A")
        self.assertNotContains(response, "학생B")
        self.assertNotContains(response, "학생기타")
        self.assertContains(response, "A 제출 보기")

    def test_submissions_partial_filters_by_choice_other(self):
        req = CollectionRequest.objects.create(
            creator=self.teacher,
            title="기타 필터 테스트",
            allow_file=False,
            allow_link=False,
            allow_text=False,
            allow_choice=True,
            choice_mode="multi",
            choice_options=["A", "B"],
            choice_allow_other=True,
            status="active",
        )
        Submission.objects.create(
            collection_request=req,
            contributor_name="학생1",
            submission_type="choice",
            choice_answers=["A"],
        )
        Submission.objects.create(
            collection_request=req,
            contributor_name="학생기타",
            submission_type="choice",
            choice_answers=[],
            choice_other_text="직접",
        )

        self.client.force_login(self.teacher)
        response = self.client.get(
            reverse("collect:submissions_partial", args=[req.id]),
            data={"choice_filter": "__other__"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "학생기타")
        self.assertNotContains(response, "학생1")
        self.assertContains(response, "기타 제출 보기")
