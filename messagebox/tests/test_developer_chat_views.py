from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import UserPolicyConsent, UserProfile
from core.policy_meta import PRIVACY_VERSION, TERMS_VERSION
from messagebox.developer_chat import get_or_create_developer_chat_thread
from messagebox.models import DeveloperChatMessage


User = get_user_model()


def _create_user(username, *, nickname=None, is_staff=False):
    user = User.objects.create_user(
        username=username,
        password="pw12345",
        email=f"{username}@example.com",
    )
    user.is_staff = is_staff
    user.save(update_fields=["is_staff"])
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.nickname = nickname or username
    profile.role = "school"
    profile.save(update_fields=["nickname", "role"])
    if is_staff:
        UserPolicyConsent.objects.create(
            user=user,
            provider="direct",
            terms_version=TERMS_VERSION,
            privacy_version=PRIVACY_VERSION,
            agreed_at=user.date_joined,
            agreement_source="required_gate",
        )
    return user


class DeveloperChatViewTests(TestCase):
    def setUp(self):
        self.teacher = _create_user("chat_teacher", nickname="채팅교사")
        self.other_teacher = _create_user("other_teacher", nickname="다른교사")
        self.admin = _create_user("chat_admin", nickname="운영관리자", is_staff=True)

    def test_regular_user_page_creates_single_thread_and_renders_chat_surface(self):
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("messagebox:developer_chat"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-developer-chat-root="true"')
        self.assertContains(response, "개발자야 도와줘")
        self.assertTrue(response.context["developer_chat_initial_thread_id"])
        self.assertEqual(get_or_create_developer_chat_thread(self.teacher).participant, self.teacher)

    def test_admin_threads_api_lists_active_conversations_by_latest_message(self):
        first_thread = get_or_create_developer_chat_thread(self.teacher)
        second_thread = get_or_create_developer_chat_thread(self.other_teacher)
        DeveloperChatMessage.objects.create(
            thread=first_thread,
            sender=self.teacher,
            sender_role=DeveloperChatMessage.SenderRole.USER,
            body="먼저 보낸 문의",
        )
        DeveloperChatMessage.objects.create(
            thread=second_thread,
            sender=self.other_teacher,
            sender_role=DeveloperChatMessage.SenderRole.USER,
            body="가장 최근 문의",
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("messagebox:developer_chat_threads"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["threads"]), 2)
        self.assertEqual(payload["threads"][0]["participant_name"], "다른교사")
        self.assertEqual(payload["threads"][1]["participant_name"], "채팅교사")

    def test_regular_user_cannot_read_other_users_thread_detail(self):
        other_thread = get_or_create_developer_chat_thread(self.other_teacher)
        DeveloperChatMessage.objects.create(
            thread=other_thread,
            sender=self.other_teacher,
            sender_role=DeveloperChatMessage.SenderRole.USER,
            body="다른 사람 문의",
        )
        self.client.force_login(self.teacher)

        response = self.client.get(
            reverse("messagebox:developer_chat_thread_detail", kwargs={"thread_id": other_thread.id})
        )

        self.assertEqual(response.status_code, 403)

    def test_send_message_api_creates_admin_reply_and_updates_assignment(self):
        thread = get_or_create_developer_chat_thread(self.teacher)
        DeveloperChatMessage.objects.create(
            thread=thread,
            sender=self.teacher,
            sender_role=DeveloperChatMessage.SenderRole.USER,
            body="기능 요청이 있어요",
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("messagebox:developer_chat_send_message", kwargs={"thread_id": thread.id}),
            data='{"body":"확인하고 바로 답장드릴게요."}',
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        thread.refresh_from_db()
        self.assertEqual(thread.assigned_admin, self.admin)
        self.assertEqual(thread.last_message_sender_role, DeveloperChatMessage.SenderRole.ADMIN)
        self.assertEqual(thread.messages.count(), 2)
        self.assertEqual(response.json()["thread"]["assigned_admin_name"], "운영관리자")

    def test_mark_read_api_clears_user_unread_count_after_admin_reply(self):
        thread = get_or_create_developer_chat_thread(self.teacher)
        DeveloperChatMessage.objects.create(
            thread=thread,
            sender=self.admin,
            sender_role=DeveloperChatMessage.SenderRole.ADMIN,
            body="답장을 보냈습니다.",
        )
        self.client.force_login(self.teacher)

        before_response = self.client.get(reverse("messagebox:developer_chat_threads"))
        self.assertEqual(before_response.json()["threads"][0]["unread_count"], 1)

        response = self.client.post(
            reverse("messagebox:developer_chat_mark_read", kwargs={"thread_id": thread.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["unread_count"], 0)
