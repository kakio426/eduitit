from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from fortune.models import ChatSession, ChatMessage, UserSajuProfile, FortuneResult
from fortune.views_chat import _select_prior_general_results
from unittest.mock import patch, MagicMock
import sys

User = get_user_model()

class TestChatViews(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password', email='test@example.com')
        self.assertTrue(self.client.login(username='testuser', password='password'))
        
        self.profile = UserSajuProfile.objects.create(
            user=self.user,
            profile_name='MyProfile',
            person_name='TestUser',
            birth_year=1990,
            birth_month=1,
            birth_day=1,
            birth_hour=12,
            calendar_type='solar',
            gender='male'
        )
        self.create_url = reverse('fortune:create_chat_session')
        self.send_url = reverse('fortune:send_chat_message')

    def test_create_session(self):
        """Test creating a new chat session."""
        response = self.client.post(self.create_url, {'profile_id': self.profile.id}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        # Should redirect or return success HTML (HTMX)
        # Assuming it redirects to chat room or returns chat room partial
        if response.status_code == 302:
            pass # sys.stderr.write(f"DEBUG REDIRECT: {response.url}\n")
        
        self.assertTrue(response.status_code in [200, 302])
        
        # Check session created
        session = ChatSession.objects.filter(user=self.user, is_active=True).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.profile, self.profile)

    @patch('fortune.views_chat.get_ai_response_stream')
    def test_send_message_flow(self, mock_stream):
        """Test sending a message and receiving streamed response."""
        # Create session first
        session = ChatSession.objects.create(user=self.user, profile=self.profile)
        
        # Mock generator response
        mock_stream.return_value = iter(["Hello", " ", "Student"])
        
        response = self.client.post(self.send_url, {
            'session_id': session.id,
            'message': 'Hello teacher'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        if response.status_code != 200:
             print(f"DEBUG SEND: {response.status_code}, {response.content}")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.streaming)
        
        # Verify message saved
        self.assertTrue(ChatMessage.objects.filter(session=session, role='user', content='Hello teacher').exists())
        
        # Verify AI message saved (might be done after stream finishes or handled differently in test)
        # Note: In a real streaming response, the saving happens in the generator or after.
        # This test might need adjustment based on implementation detail.

    def test_session_turns_limit(self):
        """Test that session limits are enforced."""
        session = ChatSession.objects.create(
            user=self.user, 
            profile=self.profile,
            current_turns=10, 
            max_turns=10
        )
        
        response = self.client.post(self.send_url, {
            'session_id': session.id,
            'message': 'Over limit'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        # Should return error or specific HTMX partial indicating limit reached
        self.assertContains(response, "상담 횟수", status_code=200) # Check for limit message
        
        # Message should not be saved
        self.assertFalse(ChatMessage.objects.filter(content='Over limit').exists())

    def test_single_active_session(self):
        """Test that creating a new session deactivates the old one."""
        old_session = ChatSession.objects.create(user=self.user, profile=self.profile, is_active=True)
        
        # Create new session via view
        self.client.post(self.create_url, {'profile_id': self.profile.id}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        old_session.refresh_from_db()
        self.assertFalse(old_session.is_active)
        
        new_session = ChatSession.objects.filter(user=self.user, is_active=True).first()
        self.assertNotEqual(old_session.id, new_session.id)

    def test_save_chat(self):
        """Test saving chat history."""
        session = ChatSession.objects.create(user=self.user, profile=self.profile)
        ChatMessage.objects.create(session=session, role='user', content='Hello')
        ChatMessage.objects.create(session=session, role='assistant', content='Hi there')
        
        save_url = reverse('fortune:save_chat_to_history')
        response = self.client.post(save_url, {'session_id': session.id}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(FortuneResult.objects.filter(user=self.user, mode='teacher').exists())
        result = FortuneResult.objects.first()
        self.assertIn('Hello', result.result_text)
        self.assertIn('Hi there', result.result_text)

    def test_select_prior_general_results_excludes_teacher_and_prefers_matching_chart(self):
        target_chart = {
            "year": {"stem": "甲", "branch": "子"},
            "month": {"stem": "乙", "branch": "丑"},
            "day": {"stem": "丙", "branch": "寅"},
            "hour": {"stem": "丁", "branch": "卯"},
        }
        self.profile.natal_chart = target_chart
        self.profile.save(update_fields=["natal_chart"])

        FortuneResult.objects.create(
            user=self.user,
            mode="teacher",
            natal_chart=target_chart,
            result_text="teacher result should not be included",
        )
        FortuneResult.objects.create(
            user=self.user,
            mode="general",
            natal_chart={"day": ["丙", "寅"], "year": "甲子", "month": "乙丑", "hour": "丁卯"},
            result_text="matching general result",
        )
        FortuneResult.objects.create(
            user=self.user,
            mode="general",
            natal_chart={"day": {"stem": "庚", "branch": "午"}},
            result_text="non matching general result",
        )

        results = _select_prior_general_results(self.user, self.profile.natal_chart, limit=2)

        self.assertEqual(len(results), 1)
        self.assertIn("matching general result", results[0]["result_text"])

    def test_select_prior_general_results_falls_back_when_no_matching_chart(self):
        self.profile.natal_chart = {
            "year": {"stem": "甲", "branch": "子"},
            "month": {"stem": "乙", "branch": "丑"},
            "day": {"stem": "丙", "branch": "寅"},
            "hour": {"stem": "丁", "branch": "卯"},
        }
        self.profile.save(update_fields=["natal_chart"])

        FortuneResult.objects.create(
            user=self.user,
            mode="general",
            natal_chart={"year": "庚午", "month": "辛未", "day": "壬申", "hour": "癸酉"},
            result_text="other chart general result",
        )

        results = _select_prior_general_results(self.user, self.profile.natal_chart, limit=2)
        self.assertEqual(len(results), 1)
        self.assertIn("other chart general result", results[0]["result_text"])

class TestChatViewsFallback(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='fallbackuser', password='password', email='fallback@example.com')

    def test_returns_latest_general_when_no_match(self):
        FortuneResult.objects.create(
            user=self.user,
            mode='general',
            natal_chart={'year': 'ZZ', 'month': 'YY', 'day': 'XX', 'hour': 'WW'},
            result_text='latest general fallback',
        )
        target_chart = {
            'year': {'stem': 'A', 'branch': 'B'},
            'month': {'stem': 'C', 'branch': 'D'},
            'day': {'stem': 'E', 'branch': 'F'},
            'hour': {'stem': 'G', 'branch': 'H'},
        }

        results = _select_prior_general_results(self.user, target_chart, limit=2)

        self.assertEqual(len(results), 1)
        self.assertIn('latest general fallback', results[0]['result_text'])

    def test_returns_latest_general_when_profile_chart_missing(self):
        FortuneResult.objects.create(
            user=self.user,
            mode='general',
            natal_chart={'year': 'AA', 'month': 'BB', 'day': 'CC', 'hour': 'DD'},
            result_text='latest without profile chart',
        )

        results = _select_prior_general_results(self.user, {}, limit=2)

        self.assertEqual(len(results), 1)
        self.assertIn('latest without profile chart', results[0]['result_text'])
