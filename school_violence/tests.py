from django.test import TestCase
from django.contrib.auth.models import User
from .models import ChatSession

class ChatSessionModelTest(TestCase):
    def test_create_chat_session(self):
        pass
        # user = User.objects.create_user(username='teacher', password='pw')
        # session = ChatSession.objects.create(
        #     user=user,
        #     topic="학교폭력 신고 절차 문의",
        #     mode="homeroom"
        # )
        # self.assertEqual(ChatSession.objects.count(), 1)
        # self.assertEqual(session.mode, "homeroom")
