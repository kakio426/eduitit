import uuid
import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import UserProfile
from happy_seed.models import HSClassroom
from seed_quiz.models import SQRagDailyUsage, SQQuizBank, SQQuizBankItem, SQQuizSet

User = get_user_model()


def _make_teacher(username):
    teacher = User.objects.create_user(
        username=username, password="pw", email=f"{username}@test.com"
    )
    UserProfile.objects.update_or_create(
        user=teacher, defaults={"nickname": username, "role": "school"}
    )
    return teacher

VALID_AI_RESPONSE = {
    "items": [
        {
            "question_text": "우리나라 수도는?",
            "choices": ["부산", "서울", "대구", "인천"],
            "correct_index": 1,
            "explanation": "서울입니다.",
            "difficulty": "easy",
        },
        {
            "question_text": "1+1은?",
            "choices": ["1", "2", "3", "4"],
            "correct_index": 1,
            "explanation": "2입니다.",
            "difficulty": "easy",
        },
        {
            "question_text": "태양은 어디서 뜨나요?",
            "choices": ["서쪽", "남쪽", "동쪽", "북쪽"],
            "correct_index": 2,
            "explanation": "동쪽에서 뜹니다.",
            "difficulty": "easy",
        },
    ]
}


class TeacherFlowTest(TestCase):
    def setUp(self):
        self.teacher = _make_teacher("tf_teacher")
        self.other_teacher = _make_teacher("tf_other")
        self.classroom = HSClassroom.objects.create(
            name="흐름 테스트반",
            teacher=self.teacher,
            slug=f"flow-{uuid.uuid4().hex[:6]}",
        )
        self.client = Client()
        self.client.force_login(self.teacher)
        self.bank = SQQuizBank.objects.create(
            title="공식 상식 기본 세트",
            preset_type="orthography",
            grade=3,
            source="manual",
            is_official=True,
            is_public=False,
            is_active=True,
            created_by=self.teacher,
        )
        SQQuizBankItem.objects.create(
            bank=self.bank,
            order_no=1,
            question_text="대한민국 수도는?",
            choices=["부산", "서울", "대구", "광주"],
            correct_index=1,
            explanation="서울입니다.",
            difficulty="easy",
        )
        SQQuizBankItem.objects.create(
            bank=self.bank,
            order_no=2,
            question_text="1+1은?",
            choices=["1", "2", "3", "4"],
            correct_index=1,
            explanation="2입니다.",
            difficulty="easy",
        )
        SQQuizBankItem.objects.create(
            bank=self.bank,
            order_no=3,
            question_text="지구는 어느 행성계에 있나요?",
            choices=["은하수", "태양계", "안드로메다", "명왕성계"],
            correct_index=1,
            explanation="태양계입니다.",
            difficulty="easy",
        )

    def test_dashboard_returns_200(self):
        url = reverse(
            "seed_quiz:teacher_dashboard",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "오늘의 퀴즈 선택")
        self.assertContains(resp, 'id="csv-client-check"')
        self.assertContains(resp, "정확히 3문항 필요")

    def test_download_csv_template(self):
        url = reverse(
            "seed_quiz:download_csv_template",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv; charset=utf-8")
        body = resp.content.decode("utf-8-sig")
        self.assertIn("set_title,preset_type,grade", body)
        self.assertIn("orthography", body)
        self.assertIn("SQ-orthography-basic-L1-G3-S001-V1", body)

    def test_download_csv_error_report_requires_valid_token(self):
        url = reverse(
            "seed_quiz:download_csv_error_report",
            kwargs={"classroom_id": self.classroom.id, "token": "invalid-token"},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_topic_summary_returns_200(self):
        url = reverse(
            "seed_quiz:htmx_topic_summary",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "주제별 운영 요약")

    def test_other_teacher_forbidden(self):
        other_client = Client()
        other_client.force_login(self.other_teacher)
        url = reverse(
            "seed_quiz:teacher_dashboard",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = other_client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_bank_browse_returns_official_list(self):
        url = reverse(
            "seed_quiz:htmx_bank_browse",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.get(url, {"preset_type": "orthography", "grade": "3", "scope": "official"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "공식 상식 기본 세트")

    def test_bank_browse_with_all_grade_includes_other_grades(self):
        bank2 = SQQuizBank.objects.create(
            title="공식 맞춤법 심화 세트",
            preset_type="orthography",
            grade=4,
            source="manual",
            is_official=True,
            is_public=False,
            is_active=True,
            created_by=self.teacher,
        )
        for idx in range(1, 4):
            SQQuizBankItem.objects.create(
                bank=bank2,
                order_no=idx,
                question_text=f"문제 {idx}",
                choices=["A", "B", "C", "D"],
                correct_index=0,
                explanation="",
                difficulty="easy",
            )
        url = reverse(
            "seed_quiz:htmx_bank_browse",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.get(url, {"preset_type": "orthography", "grade": "all", "scope": "official"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "공식 상식 기본 세트")
        self.assertContains(resp, "공식 맞춤법 심화 세트")

    def test_bank_random_select_returns_preview(self):
        url = reverse(
            "seed_quiz:htmx_bank_random_select",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.post(url, {"preset_type": "orthography", "grade": "all", "scope": "official"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "선택된 퀴즈 미리보기")

    def test_bank_browse_hides_future_official_set(self):
        SQQuizBank.objects.create(
            title="내일 공개 공식 세트",
            preset_type="orthography",
            grade=3,
            source="ai",
            is_official=True,
            quality_status="approved",
            available_from=timezone.localdate() + timedelta(days=1),
            created_by=self.teacher,
        )
        url = reverse(
            "seed_quiz:htmx_bank_browse",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.get(url, {"preset_type": "orthography", "grade": "3", "scope": "official"})
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "내일 공개 공식 세트")

    def test_bank_browse_public_hides_unapproved(self):
        SQQuizBank.objects.create(
            title="미승인 공개 세트",
            preset_type="orthography",
            grade=3,
            source="csv",
            is_public=True,
            share_opt_in=True,
            quality_status="review",
            created_by=self.other_teacher,
        )
        url = reverse(
            "seed_quiz:htmx_bank_browse",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.get(url, {"preset_type": "orthography", "grade": "3", "scope": "public"})
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "미승인 공개 세트")

    def test_bank_browse_all_includes_my_review_set(self):
        SQQuizBank.objects.create(
            title="내 검토대기 세트",
            preset_type="orthography",
            grade=3,
            source="csv",
            is_public=False,
            share_opt_in=True,
            quality_status="review",
            created_by=self.teacher,
        )
        url = reverse(
            "seed_quiz:htmx_bank_browse",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.get(url, {"preset_type": "orthography", "grade": "3", "scope": "all"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "내 검토대기 세트")

    def test_bank_select_creates_draft_preview(self):
        url = reverse(
            "seed_quiz:htmx_bank_select",
            kwargs={"classroom_id": self.classroom.id, "bank_id": self.bank.id},
        )
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "선택된 퀴즈 미리보기")
        draft = SQQuizSet.objects.filter(classroom=self.classroom, status="draft").first()
        self.assertIsNotNone(draft)
        self.assertEqual(draft.source, "bank")
        self.assertEqual(draft.items.count(), 3)

    def test_bank_select_rejects_non_three_items(self):
        SQQuizBankItem.objects.create(
            bank=self.bank,
            order_no=4,
            question_text="추가 문항",
            choices=["A", "B", "C", "D"],
            correct_index=0,
            explanation="",
            difficulty="easy",
        )
        url = reverse(
            "seed_quiz:htmx_bank_select",
            kwargs={"classroom_id": self.classroom.id, "bank_id": self.bank.id},
        )
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("정확히 3문항", resp.content.decode("utf-8"))

    def test_csv_upload_creates_bank(self):
        csv_text = (
            "set_title,preset_type,grade,question_text,choice_1,choice_2,choice_3,choice_4,correct_index,explanation,difficulty\n"
            "SQ-orthography-basic-L1-G3-S010-V1,orthography,3,대한민국 수도는?,부산,서울,대구,광주,1,서울입니다,easy\n"
            "SQ-orthography-basic-L1-G3-S010-V1,orthography,3,1+1은?,1,2,3,4,1,2입니다,easy\n"
            "SQ-orthography-basic-L1-G3-S010-V1,orthography,3,바다 색은?,파랑,빨강,검정,흰색,0,파랑이 일반적입니다,easy\n"
        )
        from django.core.files.uploadedfile import SimpleUploadedFile

        url = reverse(
            "seed_quiz:htmx_csv_upload",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.post(
            url,
            {"csv_file": SimpleUploadedFile("quiz.csv", csv_text.encode("utf-8"), content_type="text/csv")},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "CSV 미리보기 완료")

        match = re.search(r'name="preview_token" value="([^"]+)"', resp.content.decode("utf-8"))
        self.assertIsNotNone(match)
        token = match.group(1)

        confirm_url = reverse(
            "seed_quiz:htmx_csv_confirm",
            kwargs={"classroom_id": self.classroom.id},
        )
        confirm_resp = self.client.post(confirm_url, {"preview_token": token})
        self.assertEqual(confirm_resp.status_code, 200)
        self.assertContains(confirm_resp, "CSV 저장이 완료되었습니다")
        self.assertTrue(
            SQQuizBank.objects.filter(title="SQ-orthography-basic-L1-G3-S010-V1", source="csv").exists()
        )

    def test_csv_upload_rejects_invalid_set_title_format(self):
        csv_text = (
            "set_title,preset_type,grade,question_text,choice_1,choice_2,choice_3,choice_4,correct_index,explanation,difficulty\n"
            "CSV 세트 A,orthography,3,대한민국 수도는?,부산,서울,대구,광주,1,서울입니다,easy\n"
            "CSV 세트 A,orthography,3,1+1은?,1,2,3,4,1,2입니다,easy\n"
            "CSV 세트 A,orthography,3,바다 색은?,파랑,빨강,검정,흰색,0,파랑이 일반적입니다,easy\n"
        )
        from django.core.files.uploadedfile import SimpleUploadedFile

        url = reverse(
            "seed_quiz:htmx_csv_upload",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.post(
            url,
            {"csv_file": SimpleUploadedFile("quiz.csv", csv_text.encode("utf-8"), content_type="text/csv")},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertContains(resp, "set_title 형식이 올바르지 않습니다", status_code=400)
        body = resp.content.decode("utf-8")
        report_match = re.search(r'href="([^"]+/csv-error-report/[^"]+/)"', body)
        self.assertIsNotNone(report_match)
        report_url = report_match.group(1)
        report_resp = self.client.get(report_url)
        self.assertEqual(report_resp.status_code, 200)
        report_body = report_resp.content.decode("utf-8-sig")
        self.assertIn("no,error_message", report_body)
        self.assertIn("set_title 형식이 올바르지 않습니다", report_body)

    @override_settings(SEED_QUIZ_CSV_MAX_ROWS=2)
    def test_csv_upload_rejects_when_row_limit_exceeded(self):
        csv_text = (
            "set_title,preset_type,grade,question_text,choice_1,choice_2,choice_3,choice_4,correct_index,explanation,difficulty\n"
            "SQ-orthography-basic-L1-G3-S020-V1,orthography,3,대한민국 수도는?,부산,서울,대구,광주,1,서울입니다,easy\n"
            "SQ-orthography-basic-L1-G3-S020-V1,orthography,3,1+1은?,1,2,3,4,1,2입니다,easy\n"
            "SQ-orthography-basic-L1-G3-S020-V1,orthography,3,바다 색은?,파랑,빨강,검정,흰색,0,파랑이 일반적입니다,easy\n"
        )
        from django.core.files.uploadedfile import SimpleUploadedFile

        url = reverse(
            "seed_quiz:htmx_csv_upload",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.post(
            url,
            {"csv_file": SimpleUploadedFile("quiz.csv", csv_text.encode("utf-8"), content_type="text/csv")},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertContains(resp, "CSV 행 수가 제한(2행)을 초과했습니다.", status_code=400)

    @override_settings(SEED_QUIZ_CSV_MAX_SETS=1)
    def test_csv_upload_rejects_when_set_limit_exceeded(self):
        csv_text = (
            "set_title,preset_type,grade,question_text,choice_1,choice_2,choice_3,choice_4,correct_index,explanation,difficulty\n"
            "SQ-orthography-basic-L1-G3-S021-V1,orthography,3,문제1,가,나,다,라,0,해설,easy\n"
            "SQ-orthography-basic-L1-G3-S021-V1,orthography,3,문제2,가,나,다,라,1,해설,easy\n"
            "SQ-orthography-basic-L1-G3-S021-V1,orthography,3,문제3,가,나,다,라,2,해설,easy\n"
            "SQ-vocabulary-basic-L1-G3-S022-V1,vocabulary,3,문제4,가,나,다,라,0,해설,easy\n"
            "SQ-vocabulary-basic-L1-G3-S022-V1,vocabulary,3,문제5,가,나,다,라,1,해설,easy\n"
            "SQ-vocabulary-basic-L1-G3-S022-V1,vocabulary,3,문제6,가,나,다,라,2,해설,easy\n"
        )
        from django.core.files.uploadedfile import SimpleUploadedFile

        url = reverse(
            "seed_quiz:htmx_csv_upload",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.post(
            url,
            {"csv_file": SimpleUploadedFile("quiz.csv", csv_text.encode("utf-8"), content_type="text/csv")},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertContains(resp, "CSV 세트 수가 제한(1세트)을 초과했습니다.", status_code=400)

    @override_settings(SEED_QUIZ_CSV_MAX_FILE_BYTES=120)
    def test_csv_upload_rejects_when_file_size_exceeded(self):
        csv_text = (
            "set_title,preset_type,grade,question_text,choice_1,choice_2,choice_3,choice_4,correct_index,explanation,difficulty\n"
            "SQ-orthography-basic-L1-G3-S023-V1,orthography,3,대한민국 수도는 어디인가요?,부산,서울,대구,광주,1,서울입니다,easy\n"
            "SQ-orthography-basic-L1-G3-S023-V1,orthography,3,1+1은?,1,2,3,4,1,2입니다,easy\n"
            "SQ-orthography-basic-L1-G3-S023-V1,orthography,3,바다 색은?,파랑,빨강,검정,흰색,0,파랑이 일반적입니다,easy\n"
        )
        from django.core.files.uploadedfile import SimpleUploadedFile

        url = reverse(
            "seed_quiz:htmx_csv_upload",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.post(
            url,
            {"csv_file": SimpleUploadedFile("quiz.csv", csv_text.encode("utf-8"), content_type="text/csv")},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertContains(resp, "CSV 파일 용량이 제한을 초과했습니다.", status_code=400)

    def test_csv_confirm_with_share_opt_in_sets_review_status(self):
        csv_text = (
            "set_title,preset_type,grade,question_text,choice_1,choice_2,choice_3,choice_4,correct_index,explanation,difficulty\n"
            "SQ-orthography-basic-L1-G3-S011-V1,orthography,3,대한민국 수도는?,부산,서울,대구,광주,1,서울입니다,easy\n"
            "SQ-orthography-basic-L1-G3-S011-V1,orthography,3,1+1은?,1,2,3,4,1,2입니다,easy\n"
            "SQ-orthography-basic-L1-G3-S011-V1,orthography,3,바다 색은?,파랑,빨강,검정,흰색,0,파랑이 일반적입니다,easy\n"
        )
        from django.core.files.uploadedfile import SimpleUploadedFile

        upload_url = reverse(
            "seed_quiz:htmx_csv_upload",
            kwargs={"classroom_id": self.classroom.id},
        )
        upload_resp = self.client.post(
            upload_url,
            {"csv_file": SimpleUploadedFile("quiz.csv", csv_text.encode("utf-8"), content_type="text/csv")},
        )
        self.assertEqual(upload_resp.status_code, 200)

        match = re.search(r'name="preview_token" value="([^"]+)"', upload_resp.content.decode("utf-8"))
        self.assertIsNotNone(match)
        token = match.group(1)

        confirm_url = reverse(
            "seed_quiz:htmx_csv_confirm",
            kwargs={"classroom_id": self.classroom.id},
        )
        confirm_resp = self.client.post(
            confirm_url,
            {"preview_token": token, "share_opt_in": "on"},
        )
        self.assertEqual(confirm_resp.status_code, 200)
        bank = SQQuizBank.objects.get(
            title="SQ-orthography-basic-L1-G3-S011-V1",
            source="csv",
            created_by=self.teacher,
        )
        self.assertEqual(bank.quality_status, "review")
        self.assertFalse(bank.is_public)
        self.assertTrue(bank.share_opt_in)

    def test_csv_confirm_fails_when_preview_expired(self):
        confirm_url = reverse(
            "seed_quiz:htmx_csv_confirm",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.post(confirm_url, {"preview_token": "expired-token"})
        self.assertEqual(resp.status_code, 400)
        self.assertContains(resp, "세션이 만료", status_code=400)

    @override_settings(SEED_QUIZ_RAG_DAILY_LIMIT=1, SEED_QUIZ_ALLOW_RAG=True)
    @patch("seed_quiz.views.generate_bank_from_context_ai")
    def test_rag_generate_returns_preview_and_consumes_quota(self, mock_generate):
        mock_generate.return_value = self.bank
        url = reverse(
            "seed_quiz:htmx_rag_generate",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.post(
            url,
            {"preset_type": "orthography", "grade": "3", "source_text": "오늘 읽은 글 지문입니다."},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "지문 기반 맞춤 생성 완료")
        self.assertContains(resp, "대한민국 수도는?")
        usage = SQRagDailyUsage.objects.get(
            usage_date=timezone.localdate(),
            classroom=self.classroom,
            teacher=self.teacher,
        )
        self.assertEqual(usage.count, 1)

    @override_settings(SEED_QUIZ_RAG_DAILY_LIMIT=1, SEED_QUIZ_ALLOW_RAG=True)
    def test_rag_generate_blocks_when_daily_limit_exceeded(self):
        SQRagDailyUsage.objects.create(
            usage_date=timezone.localdate(),
            classroom=self.classroom,
            teacher=self.teacher,
            count=1,
        )
        url = reverse(
            "seed_quiz:htmx_rag_generate",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.post(
            url,
            {"preset_type": "orthography", "grade": "3", "source_text": "오늘 읽은 글 지문입니다."},
        )
        self.assertEqual(resp.status_code, 429)
        self.assertIn("오늘의 맞춤 생성 횟수를 모두 사용", resp.content.decode("utf-8"))

    @override_settings(SEED_QUIZ_RAG_DAILY_LIMIT=1, SEED_QUIZ_ALLOW_RAG=True)
    @patch("seed_quiz.views.generate_bank_from_context_ai", side_effect=RuntimeError("생성 실패"))
    def test_rag_generate_refunds_quota_on_generation_error(self, _mock_generate):
        url = reverse(
            "seed_quiz:htmx_rag_generate",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.post(
            url,
            {"preset_type": "orthography", "grade": "3", "source_text": "오늘 읽은 글 지문입니다."},
        )
        self.assertEqual(resp.status_code, 400)
        usage = SQRagDailyUsage.objects.get(
            usage_date=timezone.localdate(),
            classroom=self.classroom,
            teacher=self.teacher,
        )
        self.assertEqual(usage.count, 0)

    @patch("seed_quiz.services.generation._call_ai")
    def test_generate_returns_preview(self, mock_ai):
        mock_ai.return_value = VALID_AI_RESPONSE
        url = reverse(
            "seed_quiz:htmx_generate",
            kwargs={"classroom_id": self.classroom.id},
        )
        resp = self.client.post(url, {"preset_type": "orthography", "grade": "3"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "우리나라 수도는?")

    @patch("seed_quiz.services.generation._call_ai")
    def test_publish_changes_status(self, mock_ai):
        mock_ai.return_value = VALID_AI_RESPONSE
        # 생성
        gen_url = reverse(
            "seed_quiz:htmx_generate",
            kwargs={"classroom_id": self.classroom.id},
        )
        self.client.post(gen_url, {"preset_type": "orthography", "grade": "3"})
        quiz_set = SQQuizSet.objects.filter(classroom=self.classroom).first()
        self.assertIsNotNone(quiz_set)

        # 배포
        pub_url = reverse(
            "seed_quiz:htmx_publish",
            kwargs={
                "classroom_id": self.classroom.id,
                "set_id": quiz_set.id,
            },
        )
        resp = self.client.post(pub_url)
        self.assertEqual(resp.status_code, 200)
        quiz_set.refresh_from_db()
        self.assertEqual(quiz_set.status, "published")

    @patch("seed_quiz.services.generation._call_ai")
    def test_publish_closes_existing_published(self, mock_ai):
        mock_ai.return_value = VALID_AI_RESPONSE
        gen_url = reverse(
            "seed_quiz:htmx_generate",
            kwargs={"classroom_id": self.classroom.id},
        )

        # 첫 번째 생성
        self.client.post(gen_url, {"preset_type": "orthography", "grade": "3"})
        qs1 = SQQuizSet.objects.filter(classroom=self.classroom).order_by("created_at").first()
        self.assertIsNotNone(qs1)
        pub_url = reverse(
            "seed_quiz:htmx_publish",
            kwargs={"classroom_id": self.classroom.id, "set_id": qs1.id},
        )
        self.client.post(pub_url)
        qs1.refresh_from_db()
        self.assertEqual(qs1.status, "published")

        # 두 번째 생성 (다시 생성하면 같은 draft 세트 재사용)
        self.client.post(gen_url, {"preset_type": "orthography", "grade": "3"})
        # draft가 다시 생겼는지 확인 (qs1이 published → 새 draft)
        qs2 = SQQuizSet.objects.filter(classroom=self.classroom, status="draft").first()
        self.assertIsNotNone(qs2)
        pub_url2 = reverse(
            "seed_quiz:htmx_publish",
            kwargs={"classroom_id": self.classroom.id, "set_id": qs2.id},
        )
        self.client.post(pub_url2)
        qs1.refresh_from_db()
        qs2.refresh_from_db()
        self.assertEqual(qs1.status, "closed")
        self.assertEqual(qs2.status, "published")
