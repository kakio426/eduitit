import json
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import UserPolicyConsent, UserProfile
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
from handoff.models import HandoffRosterGroup
from signatures.models import ExpectedParticipant, Signature, TrainingSession


User = get_user_model()


class SignatureTeacherFirstPagesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="signature_teacher_first",
            password="pw12345",
            email="signature_teacher_first@example.com",
        )
        UserProfile.objects.update_or_create(
            user=self.user,
            defaults={"nickname": "signature_teacher_first", "role": "school"},
        )
        self.client.force_login(self.user)

    def test_list_page_uses_teacher_first_copy_and_stage_actions(self):
        ready_session = TrainingSession.objects.create(
            title="교내 연수 참석 확인",
            instructor="강사A",
            datetime=timezone.now() + timedelta(days=1),
            location="시청각실",
            created_by=self.user,
            is_active=True,
        )
        collecting_session = TrainingSession.objects.create(
            title="부장 회의 참석 서명",
            instructor="교감",
            datetime=timezone.now() + timedelta(days=2),
            location="회의실",
            created_by=self.user,
            is_active=True,
        )
        Signature.objects.create(
            training_session=collecting_session,
            participant_name="홍길동",
            participant_affiliation="교사",
            signature_data="data:image/png;base64,SIG1",
        )
        closed_session = TrainingSession.objects.create(
            title="전달 연수 수강 확인",
            instructor="강사B",
            datetime=timezone.now() + timedelta(days=3),
            location="교실",
            created_by=self.user,
            is_active=False,
        )

        response = self.client.get(reverse("signatures:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "오늘 바로 하는 일")
        self.assertContains(response, "연수·회의 출석 서명 받기")
        self.assertContains(response, "지금 상태")
        self.assertContains(response, "공유 전")
        self.assertContains(response, "진행 중")
        self.assertContains(response, "마감됨")
        self.assertContains(response, "바로 처리")
        self.assertContains(response, "지난 기록")
        self.assertContains(response, "마감된 요청")
        self.assertContains(response, "보조 도구")
        self.assertContains(response, "서명 요청 만들기")
        self.assertContains(response, "공유 시작")
        self.assertContains(response, "참여 현황")
        self.assertContains(response, "결과 보기")
        self.assertContains(response, "PDF 다운로드")
        self.assertContains(response, "내 서명 보관함")
        self.assertContains(response, "이름 폰트 도구")
        self.assertContains(response, "참여 링크 열기")
        self.assertNotContains(response, "연수·회의 참석 서명을 링크와 QR로 간편하게 받으세요.")
        self.assertNotContains(response, "로그인 없이 참여 가능")
        self.assertNotContains(response, "휴대폰으로 바로 서명")
        self.assertNotContains(response, "링크/QR 둘 다 가능")
        self.assertNotContains(response, "학교 내부 기록용")
        self.assertNotContains(response, "직접 쓴 손서명은 참여 화면에서 저장해 두고 다시 쓰세요.")
        self.assertNotContains(response, "1. 서명 요청 만들기")
        self.assertNotContains(response, "2. 링크 또는 QR 보내기")
        self.assertNotContains(response, "3. 참여 현황 확인하기")
        self.assertContains(response, reverse("signatures:sign", kwargs={"uuid": ready_session.uuid}))
        self.assertContains(response, reverse("signatures:sign", kwargs={"uuid": collecting_session.uuid}))
        self.assertContains(response, f"{reverse('signatures:create')}?copy_from={closed_session.uuid}")
        self.assertContains(response, reverse("signatures:print_pdf", kwargs={"uuid": ready_session.uuid}))
        self.assertContains(response, reverse("signatures:print_pdf", kwargs={"uuid": collecting_session.uuid}))
        self.assertContains(response, reverse("signatures:print_pdf", kwargs={"uuid": closed_session.uuid}))
        self.assertNotContains(response, "첫 연수 만들기")
        self.assertContains(response, reverse("signatures:detail", kwargs={"uuid": ready_session.uuid}))
        self.assertContains(response, reverse("signatures:detail", kwargs={"uuid": collecting_session.uuid}))
        self.assertContains(response, reverse("signatures:detail", kwargs={"uuid": closed_session.uuid}))
        self.assertEqual(response.context["dashboard_counts"], {"ready": 1, "collecting": 1, "closed": 1})
        self.assertEqual(
            [card["stage"] for card in response.context["actionable_cards"]],
            ["ready", "collecting"],
        )
        self.assertEqual(
            [card["session"].id for card in response.context["closed_cards"]],
            [closed_session.id],
        )

    def test_list_page_empty_state_keeps_single_primary_start_point(self):
        response = self.client.get(reverse("signatures:list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "오늘 바로 하는 일")
        self.assertContains(response, "처리할 요청 없음")
        self.assertContains(response, "마감 요청 없음")
        self.assertEqual(response.context["dashboard_counts"], {"ready": 0, "collecting": 0, "closed": 0})
        self.assertEqual(len(response.context["actionable_cards"]), 0)
        self.assertEqual(len(response.context["closed_cards"]), 0)
        self.assertEqual(response.content.decode().count("서명 요청 만들기"), 1)

    def test_list_page_shows_delegate_button_for_proxy_manager(self):
        proxy_user = User.objects.create_superuser(
            username="kakio",
            password="pw12345",
            email="kakio@example.com",
        )
        UserProfile.objects.update_or_create(
            user=proxy_user,
            defaults={"nickname": "proxy_manager", "role": "school"},
        )
        UserPolicyConsent.objects.create(
            user=proxy_user,
            provider="direct",
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
            agreed_at=timezone.now(),
            agreement_source="required_gate",
            ip_address="127.0.0.1",
            user_agent="test-agent",
        )
        self.client.force_login(proxy_user)

        response = self.client.get(reverse("signatures:list"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "교사 대신 만들기")
        self.assertContains(response, f'{reverse("signatures:create")}?delegate=1')

    def test_create_page_surfaces_optional_expected_count(self):
        response = self.client.get(reverse("signatures:create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "서명 요청 만들기")
        self.assertContains(response, "제목과 시간부터 적어 주세요.")
        self.assertContains(response, "기본 정보")
        self.assertContains(response, "요청 제목")
        self.assertContains(response, "참여 방식 선택")
        self.assertContains(response, "이름으로 확인")
        self.assertContains(response, "숫자로 확인")
        self.assertContains(response, "저장된 명단 없음")
        self.assertContains(response, "추가 옵션 열기")
        self.assertContains(response, "첨부와 인쇄 제목이 필요하면 여기에 적으세요.")
        self.assertContains(response, "내 서명 보관함")
        self.assertContains(response, "이름 폰트 도구")
        self.assertContains(response, "서명이 필요하면 여기에서 열 수 있습니다.")
        self.assertContains(response, "명단 만들기")
        self.assertContains(response, "이번에는 인원 수만 적기")
        self.assertContains(response, 'data-create-form', html=False)
        self.assertContains(response, 'data-create-submit', html=False)
        self.assertNotContains(response, "기본 요청은 위 정보만으로 충분")
        self.assertNotContains(response, "직접 쓴 손서명이 기본이고")
        self.assertNotContains(response, 'fixed inset-x-4 bottom-4', html=False)

    def test_create_page_shows_secondary_roster_button_when_rosters_exist(self):
        HandoffRosterGroup.objects.create(owner=self.user, name="교무실 명단")

        response = self.client.get(reverse("signatures:create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "새 명단 만들기")
        self.assertNotContains(response, "아직 연결할 명단이 없습니다.")

    def test_prepare_roster_return_with_attachments_redirects_back_to_create_with_notice(self):
        session_dt = timezone.localtime(timezone.now() + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)
        prepare_response = self.client.post(
            reverse("signatures:prepare_roster_return"),
            data={
                "title": "첨부 후 명단 이동",
                "print_title": "",
                "instructor": "강사",
                "datetime": session_dt.strftime("%Y-%m-%dT%H:%M"),
                "location": "시청각실",
                "description": "첨부 포함",
                "expected_count": "24",
                "is_active": "on",
                "attachments": [
                    SimpleUploadedFile("guide.pdf", b"pdf-bytes", content_type="application/pdf"),
                ],
            },
        )

        self.assertEqual(prepare_response.status_code, 302)
        redirect_url = prepare_response["Location"]
        self.assertIn(reverse("handoff:dashboard"), redirect_url)

        return_to = parse_qs(urlparse(redirect_url).query)["return_to"][0]
        self.assertIn(reverse("signatures:create"), return_to)
        self.assertIn("reupload_attachments=1", return_to)
        self.assertIn("show_additional_options=1", return_to)

        restored_response = self.client.get(return_to)

        self.assertEqual(restored_response.status_code, 200)
        self.assertContains(restored_response, "첨부 파일은 명단 만들기 화면을 다녀오면 유지되지 않습니다.")
        self.assertEqual(restored_response.context["form"]["title"].value(), "첨부 후 명단 이동")
        self.assertEqual(str(restored_response.context["form"]["expected_count"].value()), "24")
        self.assertTrue(restored_response.context["attachment_reupload_notice"])

    def test_prepare_roster_return_restores_draft_and_auto_selects_roster(self):
        session_dt = timezone.localtime(timezone.now() + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)
        prepare_response = self.client.post(
            reverse("signatures:prepare_roster_return"),
            data={
                "title": "복귀 테스트 요청",
                "print_title": "",
                "instructor": "강사",
                "datetime": session_dt.strftime("%Y-%m-%dT%H:%M"),
                "location": "시청각실",
                "description": "명단 만들고 돌아옵니다.",
                "expected_count": "24",
                "is_active": "on",
            },
        )

        self.assertEqual(prepare_response.status_code, 302)
        redirect_url = prepare_response["Location"]
        self.assertIn(reverse("handoff:dashboard"), redirect_url)

        return_to = parse_qs(urlparse(redirect_url).query)["return_to"][0]
        draft_token = parse_qs(urlparse(return_to).query)["draft_token"][0]

        roster = HandoffRosterGroup.objects.create(owner=self.user, name="방금 만든 명단")
        restored_response = self.client.get(
            reverse("signatures:create"),
            data={"draft_token": draft_token, "shared_roster_group": str(roster.id)},
        )

        self.assertEqual(restored_response.status_code, 200)
        self.assertContains(restored_response, "방금 만든 명단")
        self.assertEqual(restored_response.context["form"]["title"].value(), "복귀 테스트 요청")
        self.assertEqual(str(restored_response.context["form"]["expected_count"].value()), "24")
        self.assertEqual(
            str(restored_response.context["form"]["shared_roster_group"].value()),
            str(roster.id),
        )

    def test_create_can_copy_from_existing_request_and_participants(self):
        source_session = TrainingSession.objects.create(
            title="복제할 서명 요청",
            instructor="강사",
            datetime=timezone.now() + timedelta(days=5),
            location="과학실",
            created_by=self.user,
            is_active=False,
        )
        ExpectedParticipant.objects.create(training_session=source_session, name="김교사", affiliation="1-1")
        ExpectedParticipant.objects.create(training_session=source_session, name="이교사", affiliation="1-2")

        copy_url = f"{reverse('signatures:create')}?copy_from={source_session.uuid}"
        response = self.client.get(copy_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="copy_from_uuid"', html=False)
        self.assertContains(response, "이전 요청")
        self.assertContains(response, "복제할 서명 요청")
        self.assertContains(response, "참석자 후보 2명")

        session_dt = timezone.localtime(timezone.now() + timedelta(days=6)).replace(minute=0, second=0, microsecond=0)
        post_response = self.client.post(
            copy_url,
            {
                "copy_from_uuid": str(source_session.uuid),
                "title": "복제 후 새 요청",
                "print_title": "",
                "instructor": "강사",
                "datetime": session_dt.strftime("%Y-%m-%dT%H:%M"),
                "location": "과학실",
                "description": "",
                "shared_roster_group": "",
                "expected_count": "2",
                "is_active": "on",
            },
            follow=True,
        )

        self.assertEqual(post_response.status_code, 200)
        new_session = TrainingSession.objects.get(title="복제 후 새 요청", created_by=self.user)
        self.assertTrue(new_session.is_active)
        self.assertEqual(new_session.expected_participants.count(), 2)
        self.assertContains(post_response, "이전 요청 명단 2명도 복사했습니다.")

    def test_detail_ready_stage_promotes_share_actions(self):
        session = TrainingSession.objects.create(
            title="연수 공유 전",
            instructor="강사",
            datetime=timezone.now() + timedelta(days=1),
            location="강당",
            created_by=self.user,
            is_active=True,
            expected_count=10,
        )

        response = self.client.get(reverse("signatures:detail", kwargs={"uuid": session.uuid}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["stage"], "ready")
        self.assertEqual(response.context["pending_count"], 10)
        self.assertContains(response, "이제 참여 링크를 보내세요")
        self.assertContains(response, "공유 패키지 복사")
        self.assertContains(response, "링크 복사")
        self.assertContains(response, "QR 보기", count=1)
        self.assertContains(response, "참여 현황 보기")
        self.assertContains(response, "남은 인원 확인")
        self.assertContains(response, "현장 코드")
        self.assertContains(response, "사용 안 함")
        self.assertContains(response, "5분")
        self.assertContains(response, "10분")

    def test_teacher_can_apply_access_code_from_detail_page(self):
        session = TrainingSession.objects.create(
            title="현장 코드 테스트",
            instructor="강사",
            datetime=timezone.now() + timedelta(days=1),
            location="강당",
            created_by=self.user,
            is_active=True,
        )

        response = self.client.post(
            reverse("signatures:update_access_code", kwargs={"uuid": session.uuid}),
            data=json.dumps({"duration_minutes": 10, "access_code": "5831"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.access_code_duration_minutes, 10)
        self.assertEqual(session.active_access_code, "5831")
        self.assertIsNotNone(session.active_access_code_expires_at)

    def test_detail_collecting_stage_shows_absentees(self):
        session = TrainingSession.objects.create(
            title="진행 중 요청",
            instructor="강사",
            datetime=timezone.now() + timedelta(days=1),
            location="도서실",
            created_by=self.user,
            is_active=True,
        )
        signed = Signature.objects.create(
            training_session=session,
            participant_name="김교사",
            participant_affiliation="1-1",
            signature_data="data:image/png;base64,SIG1",
        )
        participant_signed = ExpectedParticipant.objects.create(training_session=session, name="김교사", affiliation="1-1")
        participant_signed.matched_signature = signed
        participant_signed.save(update_fields=["matched_signature"])
        ExpectedParticipant.objects.create(training_session=session, name="이교사", affiliation="1-2")

        response = self.client.get(reverse("signatures:detail", kwargs={"uuid": session.uuid}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["stage"], "collecting")
        self.assertTrue(response.context["can_show_absentees"])
        self.assertEqual(response.context["pending_count"], 1)
        self.assertContains(response, "서명이 들어오고 있어요")
        self.assertContains(response, "미참여 보기")
        self.assertContains(response, "마감하기")
        self.assertContains(response, "이교사 (1-2)")

    def test_detail_closed_stage_shows_reopen_and_duplicate_actions(self):
        session = TrainingSession.objects.create(
            title="마감된 요청",
            instructor="강사",
            datetime=timezone.now() + timedelta(days=1),
            location="회의실",
            created_by=self.user,
            is_active=False,
        )

        response = self.client.get(reverse("signatures:detail", kwargs={"uuid": session.uuid}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["stage"], "closed")
        self.assertContains(response, "결과를 확인하세요")
        self.assertContains(response, "PDF 다운로드")
        self.assertContains(response, "다시 열기")
        self.assertContains(response, "복제해서 새로 만들기")
        self.assertContains(response, reverse("signatures:print_pdf", kwargs={"uuid": session.uuid}))

    def test_teacher_can_download_signed_pdf_directly(self):
        try:
            import reportlab  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("reportlab unavailable")

        session = TrainingSession.objects.create(
            title="PDF 다운로드 테스트",
            instructor="강사",
            datetime=timezone.now() + timedelta(days=1),
            location="교실",
            created_by=self.user,
            is_active=False,
        )
        Signature.objects.create(
            training_session=session,
            participant_name="홍길동",
            participant_affiliation="교사",
            signature_data="data:image/png;base64,SIG1",
        )

        response = self.client.get(reverse("signatures:print_pdf", kwargs={"uuid": session.uuid}))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(response["Cache-Control"], "no-store, private")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF"))

    def test_teacher_flow_from_create_to_public_sign_to_pdf_download_has_no_blocker(self):
        try:
            import reportlab  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("reportlab unavailable")

        session_dt = timezone.localtime(timezone.now() + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)
        create_response = self.client.post(
            reverse("signatures:create"),
            data={
                "title": "생성부터 PDF까지 확인",
                "print_title": "",
                "instructor": "강사",
                "datetime": session_dt.strftime("%Y-%m-%dT%H:%M"),
                "location": "시청각실",
                "description": "",
                "shared_roster_group": "",
                "expected_count": "5",
                "is_active": "on",
            },
            follow=True,
        )

        self.assertEqual(create_response.status_code, 200)
        self.assertContains(create_response, "서명 요청이 생성되었습니다.")
        session = TrainingSession.objects.get(title="생성부터 PDF까지 확인", created_by=self.user)

        list_ready_response = self.client.get(reverse("signatures:list"))
        self.assertEqual(list_ready_response.context["dashboard_counts"], {"ready": 1, "collecting": 0, "closed": 0})
        self.assertEqual(
            [card["stage"] for card in list_ready_response.context["actionable_cards"]],
            ["ready"],
        )
        self.assertContains(list_ready_response, reverse("signatures:print_pdf", kwargs={"uuid": session.uuid}))

        self.client.logout()
        sign_response = self.client.post(
            reverse("signatures:sign", kwargs={"uuid": session.uuid}),
            data={
                "participant_affiliation": "교사",
                "participant_name": "홍길동",
                "signature_data": "data:image/png;base64,SIG",
            },
        )

        self.assertEqual(sign_response.status_code, 200)
        self.assertContains(sign_response, "출석·참여 확인")
        self.assertTrue(Signature.objects.filter(training_session=session, participant_name="홍길동").exists())

        self.client.force_login(self.user)
        list_collecting_response = self.client.get(reverse("signatures:list"))
        self.assertEqual(list_collecting_response.context["dashboard_counts"], {"ready": 0, "collecting": 1, "closed": 0})
        self.assertEqual(
            [card["stage"] for card in list_collecting_response.context["actionable_cards"]],
            ["collecting"],
        )
        self.assertContains(list_collecting_response, "참여 현황")
        self.assertContains(list_collecting_response, reverse("signatures:print_pdf", kwargs={"uuid": session.uuid}))

        pdf_response = self.client.get(reverse("signatures:print_pdf", kwargs={"uuid": session.uuid}))

        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response["Content-Type"], "application/pdf")
        self.assertTrue(b"".join(pdf_response.streaming_content).startswith(b"%PDF"))

    def test_public_sign_page_shows_quick_participation_prompts(self):
        session = TrainingSession.objects.create(
            title="공개 참여 요청",
            instructor="강사",
            datetime=timezone.now() + timedelta(days=1),
            location="교실",
            created_by=self.user,
            is_active=True,
        )

        self.client.logout()
        response = self.client.get(reverse("signatures:sign", kwargs={"uuid": session.uuid}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "로그인 없이 참여")
        self.assertContains(response, "휴대폰으로 서명 가능")
