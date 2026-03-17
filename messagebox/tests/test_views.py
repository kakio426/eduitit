from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import UserProfile


User = get_user_model()


@override_settings(
    FEATURE_MESSAGE_CAPTURE_ENABLED=True,
    FEATURE_MESSAGE_CAPTURE_ALLOWLIST_USERNAMES="messagebox_teacher",
    FEATURE_MESSAGE_CAPTURE_ITEM_TYPES=True,
)
class MessageboxViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="messagebox_teacher",
            password="pw12345",
            email="messagebox_teacher@example.com",
        )
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.nickname = "보관함교사"
        profile.role = "school"
        profile.save(update_fields=["nickname", "role"])
        self.client.force_login(self.user)

    def test_main_renders_standalone_messagebox_surface(self):
        response = self.client.get(reverse("messagebox:main"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-messagebox-root="true"')
        self.assertContains(response, 'data-messagebox-archive="true"')
        self.assertContains(response, 'id="messagebox-compose"')
        self.assertContains(response, 'id="messagebox-archive"')
        self.assertContains(response, '@click="focusMessageArchive()"')
        self.assertContains(response, "보관만 함")
        self.assertContains(response, "캘린더 연결됨")
        self.assertContains(response, "날짜 후보 불러오는 중...")
        self.assertContains(response, ':disabled="isParsingMessageCapture || isLoadingMessageArchiveDetail"')
        self.assertContains(response, "자동으로 날짜 찾기")
        self.assertContains(response, "바로 일정 넣기")
        self.assertContains(response, "보관만 하기")
        self.assertContains(response, "직접 일정 추가")
        self.assertContains(response, "날짜 놓는 달력")
        self.assertContains(response, "선택한 후보 편집")
        self.assertContains(response, "일정 수정")
        self.assertContains(response, "일정 수정하기")
        self.assertContains(response, '<option value="meeting">회의</option>', html=True)
        self.assertContains(response, '<option value="class">수업</option>', html=True)
        self.assertContains(response, '<option value="consulting">상담</option>', html=True)
        self.assertContains(response, '<option value="training">연수</option>', html=True)
        self.assertContains(response, '<option value="exam">평가</option>', html=True)
        self.assertContains(response, "removeMessageCaptureCandidate(candidate.candidate_id)")
        self.assertContains(response, "지우기")
        self.assertContains(response, "startManualMessageCaptureFromInput()")
        self.assertContains(response, "deleteSelectedMessageArchiveCapture()")
        self.assertContains(response, "메시지 삭제")
        self.assertContains(response, "deleteSavedEventFromDone(savedEvent)")
        self.assertContains(response, "deleteLinkedItem(linked, { refreshArchive: true, captureId: selectedCaptureId() })")
        self.assertContains(response, "editSelectedArchiveCandidate(candidate.candidate_id)")
        self.assertContains(response, "addManualCandidateFromSelectedArchive()")
        self.assertNotContains(response, "날짜 연결하기")
        self.assertNotContains(response, "선택 후 오른쪽 달력 날짜를 누르세요.")
        self.assertNotContains(response, "카드의 일정 수정을 누른 뒤 달력 날짜를 정하면 됩니다.")
        self.assertNotContains(response, "일정 수정을 누르면 달력과 편집칸으로 바로 이어집니다.")
        self.assertNotContains(response, "일정 수정 후 달력 날짜를 정하세요.")
        self.assertNotContains(response, "일정 수정으로 고른 후보 날짜가 여기서 바로 바뀝니다.")
        self.assertNotContains(response, "내용을 접었다 펼 수 있어요.")
        self.assertNotContains(response, "달력으로 날짜를 옮긴 뒤 필요한 정보만 아래에서 다듬으세요.")
        self.assertNotContains(response, "직접 일정 추가를 눌러 제목과 날짜만 바로 넣을 수 있어요.")
        self.assertNotContains(response, "이 일정 삭제")

    def test_main_keeps_requested_capture_id_in_context(self):
        response = self.client.get(f"{reverse('messagebox:main')}?capture=test-capture-id")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["initial_capture_id"], "test-capture-id")
